# Recorder — Vision & North Star

> The brief. Read this before touching code. It is the *why*; everything
> else serves it. When a decision is unclear, the tie-breaker is always:
> **does this make capture more reliable and organization more frictionless?**

## The thesis

Carry a hardware voice recorder all day. One button → it's recording. Rant,
braindump, capture whatever falls out of your head — a todo ("buy milk"), a
screenplay title ("Jimmy and the Whales Go to Catatopia"), a punchline, a
reminder that someone replied to an email. Messy, mixed, unsorted, offline,
zero friction. The device already timestamps every clip.

Plug the recorder into the Mac. The app ingests everything, transcribes it,
and the LLM does the **tedious part you'd never do by hand**: figures out what
each morsel *is* and files it where it belongs — todo, reminder (with a real
time), joke, idea, log entry — so *you make zero organizing decisions*.

Then sit down at the end of the day/week to a calm review surface where it's
all there: organized, timestamped, serialized, and searchable. A vague
fragment ("that bit about whales") pulls back the whole thing.

## Who it's for

High-volume idea people: comedians, joke writers, ADHD brains. People who
*think* they'll remember and don't, and who won't fight friction to capture.

## Non-negotiables (in priority order)

1. **Reliability of capture.** If you can't trust that what you offloaded is
   actually there later, the whole premise collapses. Nothing is ever lost.
2. **Lower friction than a pen and pad.** The recorder solves capture friction
   in hardware. The Mac side must not reintroduce it.
3. **Zero-decision organization.** The system makes the filing decisions the
   user would have made. Beautiful systems abstract complexity away by doing
   fewer things, perfectly. Remove decisions, don't add them.
4. **Timestamped, searchable event log is the source of truth.** Everything
   ever said, in order, with time. Organization (todos, lists, reminders,
   joke book) is a *view* derived on top — if a categorizer mis-files, the raw
   morsel is still findable in the log.

## Hard-won lesson (why v1 failed)

The previous attempt (a phone/web "second brain" app, built over winter with
weaker models) failed from **complexity, not model capability**. A better
model is a license to *simplify*, not to expand. Build less, bulletproofed.
Do not bring vestiges of the old complicated workflows into this project.

## The hardware workflow (what changed)

Capture (offline, on-device) and processing (on the Mac, online) are now
cleanly separated — a much better fit than cramming both into a phone app.
The Mac gives far more room to make the organization actually useful.

Path: hardware recorder → plug into Mac → Mac app ingests & organizes →
review surface. Maybe later: distill the most-used features into an iOS app.

## The device (ground truth, verified 2026-06-13)

- Mounts at `/Volumes/Recorder`.
- Audio lives in `/Volumes/Recorder/record/*.wav`.
- **Filename IS the capture timestamp:** `YYYYMMDD-HHMMSS.wav`
  (e.g. `20260613-095412.wav`). Time-anchoring is free — no metadata parsing.
- Format: WAV, Microsoft PCM, **16 kHz, 16-bit, stereo**.
- `/Volumes/Recorder/DBROOT/*.db` is the device's own media library (SQLite);
  almost certainly ignorable for our purposes.
- Backlog as of first inspection: 23 clips, ~26 min, ~99 MB. Grows over time.

## Prior art to mine

`~/yapzap` — an existing hand-rolled version: Obsidian vault + `import.sh` /
`transcribe.sh` that transcribe recordings into markdown. Reveals the user's
preferred toolchain and what already works. Mine it before reinventing.

---
*Architecture decisions (stack, transcription engine, storage, review surface)
are appended below once chosen — this section above is the stable north star.*
