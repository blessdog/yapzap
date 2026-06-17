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
    transcribed_at  TEXT,                      -- ISO UTC
    organized_at    TEXT,                      -- ISO UTC; when the mind ran
    organize_prompt_version TEXT               -- prompt version used to organize
);

CREATE TABLE IF NOT EXISTS fragments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    yap_id          INTEGER NOT NULL REFERENCES yaps(id),
    type            TEXT    NOT NULL,          -- joke|idea|insight|practical
    quote           TEXT    NOT NULL,          -- VERBATIM span from transcript
    text            TEXT    NOT NULL,          -- lightly-cleaned, formalize-ready
    tags            TEXT,                      -- JSON array
    model           TEXT    NOT NULL,
    prompt_version  TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fragments_yap ON fragments(yap_id);
CREATE INDEX IF NOT EXISTS idx_fragments_type ON fragments(type);
"""

# Columns added after the first release; ensure they exist on older DBs.
_YAPS_ADDED_COLUMNS = {
    "organized_at": "TEXT",
    "organize_prompt_version": "TEXT",
}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Rollback journal (NOT WAL): the Swift app opens the DB read-only, and a
    # read-only sqlite connection can't reliably open a WAL database (it can't
    # create the -shm file). Single writer (python) + single reader (app) means
    # WAL buys nothing here. DELETE mode keeps cross-process reads dependable.
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created (DB is local data)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(yaps)")}
    for name, decl in _YAPS_ADDED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE yaps ADD COLUMN {name} {decl}")
    conn.commit()


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


# --- organization (the mind) ---------------------------------------------


def pending_organization(
    conn: sqlite3.Connection, prompt_version: str
) -> list[sqlite3.Row]:
    """Transcribed yaps not yet organized at the current prompt version.

    'empty' yaps (no speech) are skipped — there's no gold to extract.
    """
    cur = conn.execute(
        """
        SELECT * FROM yaps
         WHERE status = 'transcribed'
           AND (organize_prompt_version IS NULL OR organize_prompt_version != ?)
         ORDER BY captured_at
        """,
        (prompt_version,),
    )
    return cur.fetchall()


def insert_fragments(
    conn: sqlite3.Connection,
    yap_id: int,
    fragments: list[dict],
    *,
    model: str,
    prompt_version: str,
    created_at: str,
) -> None:
    """Replace this yap's fragments. Re-running is idempotent (delete then insert).

    Each fragment dict: {type, quote, text, tags(list)}.
    """
    import json

    conn.execute("DELETE FROM fragments WHERE yap_id = ?", (yap_id,))
    conn.executemany(
        """
        INSERT INTO fragments (yap_id, type, quote, text, tags, model,
                               prompt_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                yap_id,
                f["type"],
                f["quote"],
                f["text"],
                json.dumps(f.get("tags", [])),
                model,
                prompt_version,
                created_at,
            )
            for f in fragments
        ],
    )
    conn.commit()


def mark_organized(
    conn: sqlite3.Connection, yap_id: int, *, prompt_version: str, organized_at: str
) -> None:
    conn.execute(
        "UPDATE yaps SET organized_at = ?, organize_prompt_version = ? WHERE id = ?",
        (organized_at, prompt_version, yap_id),
    )
    conn.commit()


def fragments_for(conn: sqlite3.Connection, yap_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM fragments WHERE yap_id = ? ORDER BY id", (yap_id,)
    )
    return cur.fetchall()


def recent_fragments(
    conn: sqlite3.Connection, type_: str | None = None, limit: int = 50
) -> list[sqlite3.Row]:
    """Fragments joined to their yap's capture time, newest first."""
    sql = """
        SELECT f.*, y.captured_at AS captured_at
          FROM fragments f JOIN yaps y ON y.id = f.yap_id
    """
    params: list = []
    if type_:
        sql += " WHERE f.type = ?"
        params.append(type_)
    sql += " ORDER BY y.captured_at DESC, f.id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def fragment_type_counts(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute("SELECT type, COUNT(*) AS n FROM fragments GROUP BY type")
    return {row["type"]: row["n"] for row in cur.fetchall()}
