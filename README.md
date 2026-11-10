# Audio to Piano

Turn a piano recording into notes, clean out the noise, and get a MIDI file.

## Web app (any device)

`web/index.html` is the whole app. It runs in the browser: drop an MP3, cut the start and end,
transcribe with **Basic Pitch** (Spotify's neural network) or **Classic** (signal processing),
delete noisy notes, and download MIDI. Nothing is uploaded.

- **Live at https://recklesshogrider96.github.io/audio2notes/**
- Every push to `main` that changes `web/` republishes the site (see `.github/workflows/pages.yml`).
- To run it locally: `cd web && python3 -m http.server 8000`, then open http://localhost:8000
  (opening `index.html` directly from disk can't load the Basic Pitch model).
- `web/model/` is the Basic Pitch model (Apache 2.0, see `LICENSE-basic-pitch.txt`). The weights file is named `.wasm`
  only so artifact hosting will serve it; it is the original `group1-shard1of1.bin`.

Accuracy on the synthetic test pieces (F1, 1.0 is perfect):

| Engine | Für Elise | Ode to Joy |
|---|---|---|
| Classic | 0.90 | 0.95 |
| Basic Pitch, Balanced (default) | 0.93 | 0.95 |
| Basic Pitch, Fewer notes | 0.98 | 0.98 |

## Mac command-line version

Needs Python 3 and ffmpeg (`brew install ffmpeg`).

```bash
python3 -m venv venv && venv/bin/pip install numpy scipy
./run.sh "/path/to/clip.mp3" 8      # 8 = cut the first 8 seconds (optional)
```

`run.sh` transcribes the clip and opens the note editor in your browser. Save writes `out/<name>_edited.mid`.

| File | What it does |
|---|---|
| `transcribe.py` | Classic transcriber: MP3 to notes (JSON + MIDI) |
| `editor.py`, `player_template.html` | Local note editor server and page |
| `make_test_audio.py` | Synthesizes test recordings with known notes |
| `evaluate.py` | Scores a transcription against the known notes |
