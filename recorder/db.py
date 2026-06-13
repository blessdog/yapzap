"""SQLite source-of-truth for captured yaps.

One row per recording. The raw transcript and audio path are the bedrock;
organization/AI layers (added later) derive from this and never alter it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS yaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_filename TEXT    UNIQUE NOT NULL,   -- e.g. 20260613-095412.wav
    captured_at     TEXT,                      -- ISO local time, from filename
    imported_at     TEXT    NOT NULL,          -- ISO UTC
    raw_audio_path  TEXT    NOT NULL,          -- copy in our library
    size_bytes      INTEGER,
    duration_sec    REAL,
    confidence      REAL,
    model           TEXT,
    transcript      TEXT,
    status          TEXT    NOT NULL,          -- imported|transcribed|empty|error
    error           TEXT,
    transcribed_at  TEXT                       -- ISO UTC
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # durability + concurrent reads
    conn.executescript(SCHEMA)
    return conn


def get_by_filename(conn: sqlite3.Connection, filename: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM yaps WHERE source_filename = ?", (filename,))
    return cur.fetchone()


def insert_imported(
    conn: sqlite3.Connection,
    *,
    source_filename: str,
    captured_at: str | None,
    imported_at: str,
    raw_audio_path: str,
    size_bytes: int,
) -> int:
    """Record the capture. Committed immediately — this is the reliability floor."""
    cur = conn.execute(
        """
        INSERT INTO yaps (source_filename, captured_at, imported_at,
                          raw_audio_path, size_bytes, status)
        VALUES (?, ?, ?, ?, ?, 'imported')
        """,
        (source_filename, captured_at, imported_at, raw_audio_path, size_bytes),
    )
    conn.commit()
    rowid = cur.lastrowid
    assert rowid is not None
    return rowid


def mark_transcribed(
    conn: sqlite3.Connection,
    yap_id: int,
    *,
    transcript: str,
    duration_sec: float,
    confidence: float,
    model: str,
    transcribed_at: str,
    empty: bool = False,
) -> None:
    conn.execute(
        """
        UPDATE yaps
           SET transcript = ?, duration_sec = ?, confidence = ?, model = ?,
               transcribed_at = ?, status = ?, error = NULL
         WHERE id = ?
        """,
        (
            transcript,
            duration_sec,
            confidence,
            model,
            transcribed_at,
            "empty" if empty else "transcribed",
            yap_id,
        ),
    )
    conn.commit()


def mark_error(conn: sqlite3.Connection, yap_id: int, error: str) -> None:
    conn.execute(
        "UPDATE yaps SET status = 'error', error = ? WHERE id = ?", (error, yap_id)
    )
    conn.commit()


def pending_transcription(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Rows captured but not yet transcribed (or that errored) — safe to retry."""
    cur = conn.execute(
        "SELECT * FROM yaps WHERE status IN ('imported', 'error') ORDER BY captured_at"
    )
    return cur.fetchall()


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute("SELECT status, COUNT(*) AS n FROM yaps GROUP BY status")
    return {row["status"]: row["n"] for row in cur.fetchall()}


def recent(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM yaps ORDER BY captured_at DESC LIMIT ?", (limit,)
    )
    return cur.fetchall()
