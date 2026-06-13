# Recorder

A creativity instrument, not a productivity app. Carry a hardware voice
recorder all day; plug it into the Mac; the app ingests, transcribes, and
(eventually) helps you organize and *formalize* the ideas you barked into it.

See **[VISION.md](VISION.md)** for the thesis and design principles, and
**[docs/the-science.md](docs/the-science.md)** for the cognitive-science basis.

## Slice 1 — reliable capture (this is what exists now)

Ingest → repair audio → transcribe → land in a local SQLite source-of-truth.
The audio is copied and the row is committed **before** transcription, so a clip
is never lost if transcription fails. No LLM organization or UI yet — that's next.

### Requirements
- Python 3.11+ (no third-party packages — stdlib only)
- `ffmpeg` (`brew install ffmpeg`) — repairs the recorder's broken WAV headers
- A Deepgram API key in `.env` (see `.env.example`)

### Usage
```bash
# Ingest from the plugged-in recorder (default /Volumes/Recorder/record)
python3 -m recorder ingest

# Or from a backup folder (recurses for *.wav) — handy when unplugged
python3 -m recorder ingest --source ~/yapzap/raw

python3 -m recorder ingest --no-transcribe   # import only
python3 -m recorder stats                     # counts by status
python3 -m recorder list                      # recent yaps
python3 -m recorder show 12                   # full transcript for one
```

Captured audio and the database live under `library/` (gitignored — it's yours).
The hardware device is read-only to this tool and is never modified.
