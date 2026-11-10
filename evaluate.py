"""Score a transcription against ground truth: pitch must match, onset within 50 ms."""
import json, sys

NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def name(m):
    return f'{NAMES[m % 12]}{m // 12 - 1}'


def score(truth, est, tol=0.05):
    used = set()
    hits, offs = 0, []
    misses = []
    for t in truth:
        best = None
        for j, e in enumerate(est):
            if j in used or e['pitch'] != t['pitch']:
                continue
            d = abs(e['start'] - t['start'])
            if d <= tol and (best is None or d < best[1]):
                best = (j, d)
        if best:
            used.add(best[0]); hits += 1; offs.append(best[1])
        else:
            misses.append(t)
    extras = [e for j, e in enumerate(est) if j not in used]
    p = hits / max(1, len(est)); r = hits / max(1, len(truth))
    f1 = 2 * p * r / max(1e-9, p + r)
    return {'notes_true': len(truth), 'notes_found': len(est), 'correct': hits,
            'precision': round(p, 3), 'recall': round(r, 3), 'f1': round(f1, 3),
            'mean_timing_error_ms': round(1000 * sum(offs) / max(1, len(offs)), 1),
            'missed': [f"{name(m['pitch'])}@{m['start']:.2f}s" for m in misses],
            'extra': [f"{name(e['pitch'])}@{e['start']:.2f}s" for e in extras]}


if __name__ == '__main__':
    truth = json.load(open(sys.argv[1])); est = json.load(open(sys.argv[2]))
    print(json.dumps(score(truth, est), indent=1))
