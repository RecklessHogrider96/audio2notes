# Audio to Notes

Turn a music recording into notes you can play on **piano** or **guitar**.

**Try it:** https://recklesshogrider96.github.io/audio2notes/

Everything runs in your browser. Your audio is never uploaded.

## How it works

1. **Add a recording.** Drop in an MP3, WAV or M4A. Drag the handles to skip silence at the start or end.
2. **Transcribe.** An AI model (Spotify's Basic Pitch) finds the notes.
3. **Clean up.** Click any wrong or noisy note and press Delete. Undo brings it back.
4. **Pick an instrument.** See the notes as a piano roll or as guitar tab with a fretboard.
5. **Download.** Save a MIDI file, or a text tab for guitar.

Your work is saved in your browser, so it's still there when you come back.

## Features

- **Two transcription engines:** Basic Pitch (default, best on real recordings) or Classic (fast, best on clean audio).
- **Noise clean-up:** tiny notes that are usually noise are marked in red and can be removed in one click.
- **Guitar tab that's playable:**
  - uses real chord shapes (open C, G, Am, barre chords) and names them above the tab;
  - keeps your hand in one position and never needs more than a 4-fret stretch;
  - can simplify piano music to *melody + bass* or *melody only*;
  - supports Standard, Drop D, Half step down and DADGAD tunings, plus a capo.
- **Play it back** as notes, as the original recording, or both, at any speed.
- **Five color themes**, each with light and dark mode.
- **Animated logo** that moves with whatever is playing.
- **Simple by default:** extra options live under *Advanced settings*.

## Accuracy

Tested on synthetic recordings where the correct notes are known (1.0 = perfect):

| Engine | Für Elise | Ode to Joy |
|---|---|---|
| Basic Pitch, Balanced (default) | 0.93 | 0.95 |
| Basic Pitch, Fewer notes | 0.98 | 0.98 |
| Classic | 0.90 | 0.95 |

Real recordings with pedal, room echo or several instruments will score lower.

## Run it yourself

The whole app is one file, `web/index.html`, plus the AI model in `web/model/`.

```bash
cd web && python3 -m http.server 8000
```

Then open http://localhost:8000. Opening `index.html` directly from disk won't work, because the browser blocks loading the model that way.

**Publishing:** every push to `main` that changes `web/` updates the live site automatically (see `.github/workflows/pages.yml`).

## Mac command-line version (older)

The original Python version. It needs Python 3 and ffmpeg (`brew install ffmpeg`).

```bash
python3 -m venv venv && venv/bin/pip install numpy scipy
./run.sh "/path/to/clip.mp3" 8
```

The `8` is optional and cuts the first 8 seconds. This opens a note editor in your browser, and Save writes `out/<name>_edited.mid`.

| File | What it does |
|---|---|
| `transcribe.py` | Classic transcriber: audio to notes and MIDI |
| `editor.py`, `player_template.html` | The local note editor |
| `make_test_audio.py` | Makes test recordings with known notes |
| `evaluate.py` | Scores a transcription against the known notes |

## Credits

Basic Pitch is © Spotify AB, used under the Apache License 2.0 (see `web/model/LICENSE-basic-pitch.txt`). The model's weights file is renamed to `.wasm` only so some hosts will serve it; it is unchanged.
