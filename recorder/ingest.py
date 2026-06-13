"""Orchestrate ingest: copy off the device, persist the capture, then transcribe.

Reliability-first ordering (design principle #1): the audio is copied and the
DB row is committed BEFORE transcription runs. If transcription fails or the
process dies, the recording is already safe and the row is simply left pending
for the next run to retry. Nothing is ever silently lost.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import audio, config, db
from .transcribe import transcribe_wav


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class IngestReport:
    imported: int = 0
    skipped: int = 0
    transcribed: int = 0
    empty: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"  imported (new):    {self.imported}",
            f"  skipped (already): {self.skipped}",
            f"  transcribed:       {self.transcribed}",
            f"  empty/no speech:   {self.empty}",
            f"  errors:            {len(self.errors)}",
        ]
        for e in self.errors:
            lines.append(f"    ! {e}")
        return "\n".join(lines)


def _dest_for(filename: str, captured_at: str | None) -> Path:
    if captured_at:
        year, month = captured_at[0:4], captured_at[5:7]
    else:
        year = month = "unknown"
    return config.RAW_DIR / year / month / filename


def import_new(source: Path, conn, report: IngestReport) -> None:
    """Copy any wavs not already in the library; commit a row per new capture."""
    wavs = sorted(source.rglob("*.wav"))
    for src in wavs:
        filename = src.name
        if db.get_by_filename(conn, filename) is not None:
            report.skipped += 1
            continue

        captured_at = audio.captured_at_from_filename(filename)
        dest = _dest_for(filename, captured_at)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)  # preserves mtime; device is never modified

        db.insert_imported(
            conn,
            source_filename=filename,
            captured_at=captured_at,
            imported_at=_utc_now(),
            raw_audio_path=str(dest),
            size_bytes=dest.stat().st_size,
        )
        report.imported += 1


def transcribe_pending(conn, report: IngestReport, limit: int | None = None) -> None:
    api_key = config.deepgram_api_key()
    rows = db.pending_transcription(conn)
    if limit is not None:
        rows = rows[:limit]
    for row in rows:
        raw_path = Path(row["raw_audio_path"])
        if not raw_path.exists():
            db.mark_error(conn, row["id"], "raw audio missing")
            report.errors.append(f"{row['source_filename']}: raw audio missing")
            continue
        tmp = None
        try:
            tmp = audio.normalize_to_tempwav(raw_path)
            result = transcribe_wav(tmp, api_key)
            db.mark_transcribed(
                conn,
                row["id"],
                transcript=result.transcript,
                duration_sec=result.duration_sec,
                confidence=result.confidence,
                model=result.model,
                transcribed_at=_utc_now(),
                empty=result.is_empty,
            )
            if result.is_empty:
                report.empty += 1
            else:
                report.transcribed += 1
        except RuntimeError as e:
            db.mark_error(conn, row["id"], str(e))
            report.errors.append(f"{row['source_filename']}: {e}")
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)


def run(source: Path, *, transcribe: bool = True, limit: int | None = None) -> IngestReport:
    report = IngestReport()
    conn = db.connect(config.DB_PATH)
    try:
        if source.exists():
            import_new(source, conn, report)
        else:
            report.errors.append(f"source not found: {source}")
        if transcribe:
            transcribe_pending(conn, report, limit=limit)
    finally:
        conn.close()
    return report
