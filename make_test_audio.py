"""Synthesize piano-like test recordings of public-domain pieces, with ground truth.

Usage: python3 make_test_audio.py OUTDIR
Writes <name>.mp3 and <name>_truth.json for each piece.
"""
import json, subprocess, sys, os
import numpy as np

SR = 44100
NAMES = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def midi(name):
    pc = name[:-1]
    octave = int(name[-1])
    return 12 * (octave + 1) + NAMES[pc]


def piano_tone(m, dur, vel=0.8):
    """Additive piano-ish tone: inharmonic partials, per-partial decay, hammer noise."""
    f0 = 440.0 * 2 ** ((m - 69) / 12)
    n = int((dur + 0.6) * SR)  # include release tail
    t = np.arange(n) / SR
    out = np.zeros(n)
    B = 0.0004  # inharmonicity
    for k in range(1, 13):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        if fk > SR / 2 - 1000:
            break
        amp = 1.0 / k ** 1.1
        decay = 1.5 + 0.6 * k + f0 / 400
        out += amp * np.sin(2 * np.pi * fk * t + np.random.rand() * 6.28) * np.exp(-decay * t)
    # key release: fast fade after dur
    rel = np.ones(n)
    idx = int(dur * SR)
    rel[idx:] = np.exp(-12 * (t[idx:] - dur))
    attack = np.minimum(1, t / 0.004)
    noise = np.random.randn(n) * np.exp(-60 * t) * 0.05
    return vel * (out * rel * attack + noise)


def render(notes, path_mp3):
    end = max(n['start'] + n['dur'] for n in notes) + 1.0
    buf = np.zeros(int(end * SR) + SR)
    for n in notes:
        s = piano_tone(n['pitch'], n['dur'], n.get('vel', 0.8))
        i = int(n['start'] * SR)
        buf[i:i + len(s)] += s
    # light room reverb (simple decaying echoes) + room noise
    rev = np.zeros_like(buf)
    for d, g in [(0.023, 0.25), (0.041, 0.18), (0.067, 0.12), (0.11, 0.08)]:
        k = int(d * SR)
        rev[k:] += g * buf[:-k]
    buf = buf + rev + np.random.randn(len(buf)) * 0.002
    buf = buf / np.max(np.abs(buf)) * 0.9
    pcm = (buf * 32767).astype('<i2').tobytes()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1',
                    '-i', '-', '-b:a', '128k', path_mp3], input=pcm, check=True)


def fur_elise():
    u = 0.19  # seconds per sixteenth
    rh = [('E5', 0, 1), ('D#5', 1, 1),
          ('E5', 2, 1), ('D#5', 3, 1), ('E5', 4, 1), ('B4', 5, 1), ('D5', 6, 1), ('C5', 7, 1),
          ('A4', 8, 3), ('C4', 11, 1), ('E4', 12, 1), ('A4', 13, 1),
          ('B4', 14, 3), ('E4', 17, 1), ('G#4', 18, 1), ('B4', 19, 1),
          ('C5', 20, 3), ('E4', 23, 1), ('E5', 24, 1), ('D#5', 25, 1),
          ('E5', 26, 1), ('D#5', 27, 1), ('E5', 28, 1), ('B4', 29, 1), ('D5', 30, 1), ('C5', 31, 1),
          ('A4', 32, 3), ('C4', 35, 1), ('E4', 36, 1), ('A4', 37, 1),
          ('B4', 38, 3), ('E4', 41, 1), ('C5', 42, 1), ('B4', 43, 1),
          ('A4', 44, 6)]
    lh = []
    for start, pat in [(8, ['A2', 'E3', 'A3']), (14, ['E2', 'E3', 'G#3']), (20, ['A2', 'E3', 'A3']),
                       (32, ['A2', 'E3', 'A3']), (38, ['E2', 'E3', 'G#3']), (44, ['A2', 'E3', 'A3'])]:
        for i, p in enumerate(pat):
            lh.append((p, start + i, 3 - i))
    notes = []
    for p, s, d in rh:
        notes.append({'pitch': midi(p), 'start': s * u, 'dur': d * u, 'vel': 0.8})
    for p, s, d in lh:
        notes.append({'pitch': midi(p), 'start': s * u, 'dur': d * u, 'vel': 0.55})
    return notes


def ode_to_joy():
    """Melody with left-hand block chords: a harder, chordal test."""
    q = 0.42
    mel = ['E4', 'E4', 'F4', 'G4', 'G4', 'F4', 'E4', 'D4', 'C4', 'C4', 'D4', 'E4', 'E4', 'D4', 'D4']
    durs = [1] * 12 + [1.5, 0.5, 2]
    notes, t = [], 0.0
    for p, d in zip(mel, durs):
        notes.append({'pitch': midi(p), 'start': t, 'dur': d * q * 0.95, 'vel': 0.85})
        t += d * q
    chords = [(0, ['C3', 'E3', 'G3']), (4, ['G2', 'B2', 'D3']), (8, ['C3', 'E3', 'G3']), (12, ['G2', 'B2', 'D3'])]
    for beat, ch in chords:
        for p in ch:
            notes.append({'pitch': midi(p), 'start': beat * q, 'dur': 4 * q * 0.95, 'vel': 0.5})
    return notes


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    np.random.seed(7)
    for name, fn in [('fur_elise', fur_elise), ('ode_to_joy', ode_to_joy)]:
        notes = sorted(fn(), key=lambda n: (n['start'], n['pitch']))
        render(notes, os.path.join(out, name + '.mp3'))
        with open(os.path.join(out, name + '_truth.json'), 'w') as f:
            json.dump(notes, f)
        print(name, len(notes), 'notes')
