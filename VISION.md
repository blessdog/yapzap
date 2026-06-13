# Recorder — Vision & North Star

> The brief. Read this before touching code. It is the *why*; everything
> else serves it. When a decision is unclear, the tie-breaker is always:
> **does this make capture more reliable and organization more frictionless?**

## The thesis

**This is a creativity tool, not a productivity app.** Its purpose is to
sharpen thinking, build verbal fluency, and mine the gold out of your own
creative consciousness — to help you capture, explore, and *formalize* ideas.

Carry a hardware voice recorder all day. When lightning strikes — a joke, an
image, a line, a connection sparked by a podcast — you bark it in before it
evaporates. But **it's not all lightning**: often you just yap aloud for a
while, and the ideas start to bubble up *because* you're speaking them. The act
of verbalizing is itself generative. The recorder catches the whole stream —
the gold *and* the rambling that produces it. Think Hunter S. Thompson with a
recorder. It captures your thought bubbles.

Messy is the point. You express the half-formed thing, get it out of your head,
and it's safely captured and timestamped. Later, at the Mac, you return to the
pile and *formalize* — develop a fragment into a bit, a scene, an essay, a
screenplay title. The app is a template for writing and a place to rediscover
the brilliant (and hilarious) things you said and forgot you ever thought of.

**What it is NOT:** a reminder / calendar / to-do app. "Remember to buy eggs"
is trivial and beside the point. Such conveniences may be bolted on later, but
they are explicitly *not* the core. The core is capturing and formalizing ideas.

## Who it's for

Writers, comedians, joke writers — anyone whose best ideas arrive at random and
vanish if not caught, ADHD minds included. People who think out loud, who
generate more than they can hold, and who want to turn raw verbal sparks into
finished work.

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
5. **The review surface is Apple-Notes-grade simple.** Open it and it's
   *already there* — searchable, organized, beautiful, intuitive. No dropdown
   menus, no manual filing, no setup tax, no "productivity app" bloat. The
   intelligence lives in the INPUT (voice → machine parses/tags/organizes),
   so the surface itself stays brain-dead simple. Build to Apple's HIG: every
   extra button-push or popup is friction, and friction is the enemy. Either
   roll our own minimal surface in that spirit, or adopt an open-source app
   that already nails simplicity — never Obsidian-style configurable
   complexity. NOT another bloated options-everywhere productivity tool.

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

## Decisions so far

- **Build approach:** Pipeline-first. Build the ingest → transcribe → organize
  → *formalize* brain as a fast-iterating Python tool, perfected on real
  recordings, before wrapping it in a polished surface. Prove the useful core,
  polish the shell later.
- **Transcription:** Deepgram (cloud) for now — fast, known. Local Whisper on
  Apple Silicon is a viable later swap if full-offline/zero-cost matters.
- **Source of truth:** Local SQLite — the timestamped, searchable event log.
  Everything else is a view derived on top.
- **Review surface:** **Roll our own** (option B) — a unified, beautiful,
  Apple-HIG-simple home for ideas, over our own store. Our own notes, designed
  for capture → return → formalize. NOT Apple Notes, NOT Obsidian, NOT a
  third-party app. Seed of an eventual iOS app.
- **Apple-ecosystem projection (Reminders/Calendar):** optional bolt-on, LATER,
  for trivial productivity scraps only. Never the focus.

*Design principles from the cognitive-science research (below/TBD) feed the
surface and the formalization flow. The sections above are the stable north star.*
