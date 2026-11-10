#!/bin/bash
# One command: transcribe an MP3 and open the note editor.
# Usage: ./run.sh "/path/to/clip.mp3" [start_seconds]
#   start_seconds (optional) cuts off everything before that point first.
# Re-running with the same clip and cut skips transcription and reopens your saved edits.
set -e
cd "$(dirname "$0")"
src="$1"
start="${2:-0}"
[ -f "$src" ] || { echo "File not found: $src"; exit 1; }
name="$(basename "$src" .mp3)"
safe="$(echo "$name" | tr ' ' '_')"
mkdir -p out
stamp="$src|$start"
if [ -f "out/$safe.json" ] && [ "$(cat "out/$safe.source" 2>/dev/null)" = "$stamp" ]; then
  echo "Using the existing transcription (same clip and cut)."
else
  input="$src"
  if [ "$start" != "0" ]; then
    ffmpeg -y -loglevel error -ss "$start" -i "$src" "out/${safe}_trimmed.mp3"
    input="out/${safe}_trimmed.mp3"
    echo "Trimmed audio: $input"
  fi
  venv/bin/python transcribe.py "$input" "out/$safe"
  printf '%s' "$stamp" > "out/$safe.source"
fi
title="$name"
[ "$start" != "0" ] && title="$name (from ${start}s)"
exec venv/bin/python editor.py "out/$safe" "$title" "$start"
