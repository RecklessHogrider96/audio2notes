"""Piano audio -> notes (MIDI + JSON). Dependency-light POC: numpy, scipy, ffmpeg.

Usage: python3 transcribe.py input.mp3 out_prefix
Writes out_prefix.mid and out_prefix.json

Pipeline
  1. Decode with ffmpeg to mono 22.05 kHz.
  2. Semitone filterbank (Gabor filters, one per piano key A0..C8) -> energy envelope per key.
  3. Per-key onset novelty (rise in log energy) + peak picking.
  4. Snap onsets to broadband onsets (sharper timing for low notes).
  5. Reject candidates explained as overtones / spectral leakage of a stronger note.
  6. Note end = energy falls below a fraction of its peak (or the key is struck again).
"""
import json, subprocess, sys
import numpy as np
from scipy.signal import fftconvolve, find_peaks

SR = 22050
HOP = 220  # ~10 ms frames
LOW, HIGH = 28, 100  # E1 .. E7 (practical range for detection)


def load(path):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-ac', '1', '-ar', str(SR),
                          '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype='<f4').astype(np.float64)
    return x / (np.max(np.abs(x)) + 1e-9)


def key_envelopes(x):
    env = []
    for m in range(LOW, HIGH + 1):
        f = 440 * 2 ** ((m - 69) / 12)
        sig = 6.0 / f  # time spread (s); ~2.7% frequency spread, separates neighbouring keys
        half = int(3 * sig * SR)
        t = np.arange(-half, half + 1) / SR
        k = np.exp(-0.5 * (t / sig) ** 2) * np.exp(2j * np.pi * f * t)
        k /= np.sum(np.abs(k))
        y = np.abs(fftconvolve(x, k, mode='same'))
        env.append(y[::HOP])
    return np.array(env)  # (keys, frames)


def broadband_onsets(x):
    n = 1024
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n // 2, n // 2)), n)[::HOP]
    S = np.log1p(100 * np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)))
    flux = np.maximum(0, np.diff(S, axis=0, prepend=S[:1])).sum(axis=1)
    flux = flux / (flux.max() + 1e-9)
    peaks, _ = find_peaks(flux, height=0.08, distance=4)
    return peaks


def transcribe(path, rel_thresh=0.22, abs_thresh=0.06):
    x = load(path)
    E = key_envelopes(x)
    gmax = E.max()
    nk, nf = E.shape
    onsets = broadband_onsets(x)
    freqs = 440 * 2 ** ((np.arange(LOW, HIGH + 1) - 69) / 12)
    lags = np.maximum(2, np.round(6.0 / freqs * SR / HOP).astype(int))

    # overtone / leakage template: interval -> fraction of the note's level to explain away
    template = {12: 0.85, 19: 0.7, 24: 0.6, 28: 0.55, 31: 0.5, 34: 0.45, 36: 0.45, 38: 0.4, 40: 0.4,
                1: 0.35, -1: 0.35, 2: 0.12, -2: 0.12}

    found = []
    for o in onsets:
        inc = np.zeros(nk)
        for k in range(nk):
            L = lags[k]
            a = E[k, o:min(nf, o + L + 4)].max()
            b = E[k, max(0, o - L - 2):max(1, o - L + 1)].max() if o - L - 2 >= 0 else 0.0
            inc[k] = max(0.0, a - 1.15 * b)
        resid = inc.copy()
        picked, top = [], None
        for _ in range(10):
            k = int(np.argmax(resid))
            v = resid[k]
            if top is None:
                top = v
            if v < abs_thresh * gmax or v < rel_thresh * top:
                break
            picked.append((k, inc[k]))
            resid[k] = 0
            for iv, frac in template.items():
                j = k + iv
                if 0 <= j < nk:
                    resid[j] = max(0.0, resid[j] - frac * inc[k])
        for k, amp in picked:
            found.append({'key': k, 'pitch': LOW + k, 'frame': int(o), 'amp': float(amp)})

    # refine each onset to the 50% point of the key's energy rise (removes the early bias of
    # long low-frequency filters), snap to a nearby broadband onset, then de-duplicate per key
    for c in found:
        k, o, L = c['key'], c['frame'], lags[c['key']]
        lo, hi = max(0, o - 3 * L - 4), min(nf, o + 3 * L + 5)
        seg = E[k, lo:hi]
        pk = int(np.argmax(seg))
        base = seg[:pk + 1].min() if pk > 0 else seg[0]
        half = base + 0.5 * (seg[pk] - base)
        cross = np.where(seg[:pk + 1] >= half)[0]
        t = lo + (int(cross[0]) if len(cross) else pk)
        j = np.argmin(np.abs(onsets - t))
        if abs(onsets[j] - t) <= 5:
            t = int(onsets[j])
        c['frame'] = int(t)
        c['amp'] = float(seg[pk])
    found.sort(key=lambda c: (c['key'], c['frame']))
    dedup = []
    for c in found:
        if dedup and dedup[-1]['key'] == c['key'] and c['frame'] - dedup[-1]['frame'] <= 6:
            if c['amp'] > dedup[-1]['amp']:
                dedup[-1] = c
            continue
        dedup.append(c)
    # second overtone check now that onsets are aligned
    harm_ratio = {12: 0.75, 19: 0.6, 24: 0.6, 28: 0.55, 31: 0.5}
    found = []
    for c in dedup:
        ok = True
        for d in dedup:
            iv = c['key'] - d['key']
            if iv in harm_ratio and abs(c['frame'] - d['frame']) <= max(3, lags[d['key']]) and c['amp'] < harm_ratio[iv] * d['amp']:
                ok = False
                break
        if ok:
            found.append(c)

    # durations: follow the key's energy until it decays or the key is struck again
    notes = []
    starts = {}
    for c in found:
        starts.setdefault(c['key'], []).append(c['frame'])
    for c in found:
        nxt = [f for f in starts[c['key']] if f > c['frame']]
        limit = nxt[0] if nxt else nf
        e = E[c['key'], c['frame']:limit]
        pk = int(np.argmax(e[:20])) if len(e) else 0
        below = np.where(e[pk:] < 0.3 * e[pk])[0] if len(e) else []
        end = c['frame'] + pk + (below[0] if len(below) else max(1, len(e) - pk))
        db = 20 * np.log10(c['amp'] / gmax + 1e-9)
        vel = int(np.clip(110 + db * 2.0, 30, 120))
        notes.append({'pitch': c['pitch'], 'start': round(c['frame'] * HOP / SR, 3),
                      'dur': round(max(0.05, (end - c['frame']) * HOP / SR), 3), 'vel': vel})
    notes.sort(key=lambda n: (n['start'], n['pitch']))
    return notes


def write_midi(notes, path, tempo_bpm=120):
    tpq = 480
    tick_per_s = tpq * tempo_bpm / 60
    ev = []
    for n in notes:
        on = int(round(n['start'] * tick_per_s))
        off = int(round((n['start'] + n['dur']) * tick_per_s))
        ev.append((on, 1, bytes([0x90, n['pitch'], n['vel']])))
        ev.append((off, 0, bytes([0x80, n['pitch'], 0])))
    ev.sort(key=lambda e: (e[0], e[1]))

    def vlq(v):
        out = [v & 0x7F]
        v >>= 7
        while v:
            out.insert(0, (v & 0x7F) | 0x80)
            v >>= 7
        return bytes(out)

    trk = bytearray()
    us = int(60_000_000 / tempo_bpm)
    trk += vlq(0) + bytes([0xFF, 0x51, 0x03]) + us.to_bytes(3, 'big')
    trk += vlq(0) + bytes([0xC0, 0])  # acoustic grand
    last = 0
    for t, _, msg in ev:
        trk += vlq(t - last) + msg
        last = t
    trk += vlq(0) + bytes([0xFF, 0x2F, 0x00])
    data = b'MThd' + (6).to_bytes(4, 'big') + (0).to_bytes(2, 'big') + (1).to_bytes(2, 'big') + tpq.to_bytes(2, 'big')
    data += b'MTrk' + len(trk).to_bytes(4, 'big') + bytes(trk)
    with open(path, 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    src, prefix = sys.argv[1], sys.argv[2]
    notes = transcribe(src)
    with open(prefix + '.json', 'w') as f:
        json.dump(notes, f)
    write_midi(notes, prefix + '.mid')
    print(f'{len(notes)} notes -> {prefix}.mid, {prefix}.json')
