"""The mind — extract typed 'fragments' (the gold) from each transcript.

Reads transcribed yaps and asks Claude to lift the jokes, ideas, insights, and
practical scraps out of the raw verbal stream into structured fragments. The raw
transcript is the source of truth and is NEVER altered (VISION.md principle #2);
fragments are a view derived on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

import anthropic
from pydantic import BaseModel

from . import config, db

PROMPT_VERSION = config.ORGANIZE_PROMPT_VERSION
MODEL = config.ORGANIZE_MODEL


class Fragment(BaseModel):
    type: Literal["joke", "idea", "insight", "practical"]
    quote: str  # verbatim span copied from the transcript
    text: str  # lightly cleaned for reuse; never a summary of the whole yap
    tags: list[str]


class Extraction(BaseModel):
    fragments: list[Fragment]  # empty when the yap holds no extractable gold


SYSTEM = """\
You are the mind behind a voice-first CREATIVITY tool — not a productivity app.
A person speaks messy, half-formed thoughts into a recorder all day: jokes,
ideas, observations, the occasional errand. Your job is to mine the GOLD out of
each transcript so they can rediscover and develop it later.

Extract the distinct morsels worth keeping as "fragments". The four types:
- joke: a bit, punchline, comedic premise, or absurd observation.
- idea: a creative seed to develop later — an essay/article/screenplay/story
  premise, a concept, a "dig into this" thread.
- insight: a sharp observation, reflection, or quotable line worth keeping.
- practical: a low-priority side bucket for errands/reminders/names. Capture so
  nothing is lost, but this is NOT the point — never strain to find these.

Rules:
- `quote` MUST be copied verbatim from the transcript (the exact words). Do not
  paraphrase the quote.
- `text` is a LIGHT cleanup of that morsel — fix obvious transcription noise and
  make it readable while keeping the person's voice. It is NOT a summary of the
  whole recording, and never flattens away the idea.
- One fragment per distinct morsel. A single recording can yield several
  fragments, or none.
- Let the material set the count. Do not invent fragments to hit a number, and
  do not force-fit rambling that has no extractable gold yet — return an empty
  list when that's the honest answer. The rambling itself stays safe in the raw
  transcript regardless.
- `tags`: a few short lowercase topical tags to aid later rediscovery.
"""


def extract(transcript: str, client: anthropic.Anthropic) -> Extraction:
    """Send one transcript to Claude and return validated fragments.

    Adaptive thinking (effort defaults to high) gives the model room for the
    nuanced 'is this gold, and what kind' judgment.
    """
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract the fragments from this voice-note transcript:\n\n"
                    f"{transcript}"
                ),
            }
        ],
        output_format=Extraction,
    )
    return response.parsed_output


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class OrganizeReport:
    organized: int = 0
    fragments: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"  yaps organized:   {self.organized}",
            f"  fragments found:  {self.fragments}",
        ]
        for t in ("joke", "idea", "insight", "practical"):
            if self.by_type.get(t):
                lines.append(f"    {t:<10} {self.by_type[t]}")
        lines.append(f"  errors:           {len(self.errors)}")
        for e in self.errors:
            lines.append(f"    ! {e}")
        return "\n".join(lines)


def run(limit: int | None = None) -> OrganizeReport:
    report = OrganizeReport()
    client = anthropic.Anthropic(api_key=config.anthropic_api_key())
    conn = db.connect(config.DB_PATH)
    try:
        rows = db.pending_organization(conn, PROMPT_VERSION)
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            transcript = (row["transcript"] or "").strip()
            if not transcript:
                # transcribed but empty-bodied; nothing to mine, mark done
                db.mark_organized(
                    conn, row["id"],
                    prompt_version=PROMPT_VERSION, organized_at=_utc_now(),
                )
                report.organized += 1
                continue
            try:
                result = extract(transcript, client)
            except (anthropic.APIError, ValueError) as e:
                report.errors.append(f"{row['source_filename']}: {e}")
                continue
            frags = [f.model_dump() for f in result.fragments]
            db.insert_fragments(
                conn, row["id"], frags,
                model=MODEL, prompt_version=PROMPT_VERSION, created_at=_utc_now(),
            )
            db.mark_organized(
                conn, row["id"],
                prompt_version=PROMPT_VERSION, organized_at=_utc_now(),
            )
            report.organized += 1
            report.fragments += len(frags)
            for f in frags:
                report.by_type[f["type"]] = report.by_type.get(f["type"], 0) + 1
    finally:
        conn.close()
    return report
