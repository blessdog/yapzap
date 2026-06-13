# Recorder

A creativity instrument, not a productivity app. Carry a hardware voice
recorder all day; plug it into the Mac; the app ingests, transcribes, and
(eventually) helps you organize and *formalize* the ideas you barked into it.

See **[VISION.md](VISION.md)** for the thesis and design principles, and
**[docs/the-science.md](docs/the-science.md)** for the cognitive-science basis.

## Slice 1 — reliable capture

Ingest → repair audio → transcribe → land in a local SQLite source-of-truth.
The audio is copied and the row is committed **before** transcription, so a clip
is never lost if transcription fails.

## Slice 2 — the mind (LLM extraction)

`organize` reads each transcript and asks Claude (Opus 4.8) to lift the *gold* —
**jokes, ideas, insights, and practical scraps** — into typed `fragments`. The
raw transcript is the source of truth and is **never altered**; fragments are a
view derived on top. Idempotent and re-runnable (bump the prompt version to
re-process). No recombination, formalize-step, or UI yet — those come next.

### Requirements
- Python 3.11+
- `ffmpeg` (`brew install ffmpeg`) — repairs the recorder's broken WAV headers
- Slice 1 (ingest/transcribe) is stdlib-only. Slice 2 needs `pip install -r requirements.txt`.
- `DEEPGRAM_API_KEY` (transcription) and `ANTHROPIC_API_KEY` (the mind) in `.env`
  (see `.env.example`)

### Usage
```bash
# Ingest from the plugged-in recorder (default /Volumes/Recorder/record)
python3 -m recorder ingest

# Or from a backup folder (recurses for *.wav) — handy when unplugged
python3 -m recorder ingest --source ~/yapzap/raw

python3 -m recorder ingest --no-transcribe   # import only
python3 -m recorder organize                  # extract fragments (LLM)
python3 -m recorder organize --limit 1        # ...just one, to spot-check
python3 -m recorder stats                     # counts by status + fragment types
python3 -m recorder list                      # recent yaps
python3 -m recorder fragments --type joke     # extracted fragments, filterable
python3 -m recorder show 12                   # full transcript for one yap
```

Captured audio and the database live under `library/` (gitignored — it's yours).
The hardware device is read-only to this tool and is never modified.
