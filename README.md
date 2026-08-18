# yapzap

A creativity instrument, not a productivity app. Carry a hardware
voice recorder all day; plug it into the Mac; the app ingests,
transcribes, and lifts the gold — jokes, ideas, insights, practical
scraps — out of whatever you barked into it.

The thesis and design principles live in **[VISION.md](VISION.md)**;
the cognitive-science basis (why voice-first capture, referenced) in
**[docs/the-science.md](docs/the-science.md)**.

```
recorder mounts ─▶ copy + repair audio ─▶ commit the capture row
                                              │
                          Deepgram nova-3 transcription (retried)
                                              │
                        the mind: LLM lifts typed fragments
                        (joke / idea / insight / practical)
                                              │
                     menu-bar app: one continuous timeline
```

## The journey

**The reframe came first.** An early version pointed at productivity —
tasks, notes, organization. Wrong instrument. The reframe that stuck:
this is for *idea formalization* — the recorder catches raw creative
material at the moment it occurs, and the machine's job is to make
sure nothing captured is ever lost or invisible.

**Capture is sacred, so capture commits first.** The audio file is
copied and its row written to SQLite *before* transcription is
attempted. Transcription can fail (and did — big clips broke the pipe
mid-upload until retries landed); the recording survives regardless.
Same doctrine as the film pipeline's untouched call audio: the raw
material is the source of truth and is never altered — fragments are
a layer on top.

**Three bugs worth remembering:**

- **The broken-WAV gotcha.** The hardware recorder produces WAV files
  with lying headers when it loses power mid-recording; ffmpeg
  repairs them on ingest. Found by mining the v0 shell-script
  pipeline this app replaced.
- **The WAL trap.** The Python engine wrote SQLite in WAL mode; the
  Swift app reads the same DB read-only — and a read-only connection
  can't open a WAL database without its sidecar files, so the app
  showed *nothing* while the data sat there intact. DELETE journal
  mode made cross-process reads reliable. Mechanism, not mystery:
  two processes, two runtimes, one file — journal mode is part of the
  contract.
- **The GUI PATH trap.** The app spawns the Python engine, and
  GUI-spawned processes get a minimal PATH without `/opt/homebrew/bin`
  — so ffmpeg "didn't exist" only when launched from the app. Binaries
  are now found explicitly.

**The surface earned its shape.** The review UI went through visible
churn — day pins that swallowed the list, filters as a dropdown,
empty-week landings — and settled on one continuous stream, newest
first, filters as flat toggle pills, un-mined recordings shown so
nothing captured is invisible, and a "rediscover" slot that resurfaces
an old gem at the top. A calendar month view exists for time travel.

## Status

Working daily-use prototype: mount → ingest → transcribe → fragments →
review all run. The extraction prompt and the review surface keep
evolving with use. Screenshot of the app coming; the hardware is a
cheap dictaphone, which is the point.
