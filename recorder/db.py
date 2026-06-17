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
    organize_prompt_version TEXT,              -- prompt version used to organize
    sha256          TEXT                       -- hash of the library copy (wipe gate)
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
    created_at      TEXT    NOT NULL,
    -- User layer (never written by the LLM; survives re-extraction, see
    -- insert_fragments). The raw transcript + verbatim quote stay sacred.
    state           TEXT    NOT NULL DEFAULT 'active',  -- active|done|archived|deleted
    user_text       TEXT                       -- edited text; overrides `text` in the UI
);
CREATE INDEX IF NOT EXISTS idx_fragments_yap ON fragments(yap_id);
CREATE INDEX IF NOT EXISTS idx_fragments_type ON fragments(type);
"""

# Columns added after the first release; ensure they exist on older DBs.
_YAPS_ADDED_COLUMNS = {
    "organized_at": "TEXT",
    "organize_prompt_version": "TEXT",
    "sha256": "TEXT",
}
_FRAGMENTS_ADDED_COLUMNS = {
    "state": "TEXT NOT NULL DEFAULT 'active'",
    "user_text": "TEXT",
}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Rollback journal (NOT WAL): the Swift app opens the DB read-only, and a
    # read-only sqlite connection can't reliably open a WAL database (it can't
    # create the -shm file). DELETE mode keeps cross-process reads dependable.
    conn.execute("PRAGMA journal_mode=DELETE;")
    # The app now also writes the user layer (state/user_text). busy_timeout lets
    # python (the ingest writer) and Swift (interactive writes) serialize on the
    # file lock instead of failing with "database is locked".
    conn.execute("PRAGMA busy_timeout=3000;")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a DB was first created (DB is local data)."""
    yaps_cols = {row["name"] for row in conn.execute("PRAGMA table_info(yaps)")}
    for name, decl in _YAPS_ADDED_COLUMNS.items():
        if name not in yaps_cols:
            conn.execute(f"ALTER TABLE yaps ADD COLUMN {name} {decl}")
    frag_cols = {row["name"] for row in conn.execute("PRAGMA table_info(fragments)")}
    for name, decl in _FRAGMENTS_ADDED_COLUMNS.items():
        if name not in frag_cols:
            conn.execute(f"ALTER TABLE fragments ADD COLUMN {name} {decl}")
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
    sha256: str | None = None,
) -> int:
    """Record the capture. Committed immediately — this is the reliability floor.

    `sha256` is the hash of the library copy; it is the gate that lets us later
    delete the original off the device (see recorder/device.py).
    """
    cur = conn.execute(
        """
        INSERT INTO yaps (source_filename, captured_at, imported_at,
                          raw_audio_path, size_bytes, sha256, status)
        VALUES (?, ?, ?, ?, ?, ?, 'imported')
        """,
        (source_filename, captured_at, imported_at, raw_audio_path,
         size_bytes, sha256),
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


def set_sha256(conn: sqlite3.Connection, yap_id: int, sha256: str) -> None:
    conn.execute("UPDATE yaps SET sha256 = ? WHERE id = ?", (sha256, yap_id))
    conn.commit()


def yaps_missing_sha256(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Rows imported before hashing existed — backfill so they're wipe-eligible."""
    cur = conn.execute(
        "SELECT id, raw_audio_path FROM yaps WHERE sha256 IS NULL OR sha256 = ''"
    )
    return cur.fetchall()


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

    The user layer (state, user_text) is carried forward across re-extraction:
    we snapshot it keyed by the verbatim quote (a stable identity within a yap),
    delete, re-insert the LLM output, then re-apply the snapshot to any fragment
    whose quote matches. So bumping the prompt version never silently wipes a
    "done"/archived flag or an edit the user made.
    """
    import json

    prior = {
        row["quote"]: (row["state"], row["user_text"])
        for row in conn.execute(
            "SELECT quote, state, user_text FROM fragments WHERE yap_id = ?",
            (yap_id,),
        )
    }

    conn.execute("DELETE FROM fragments WHERE yap_id = ?", (yap_id,))
    for f in fragments:
        state, user_text = prior.get(f["quote"], ("active", None))
        conn.execute(
            """
            INSERT INTO fragments (yap_id, type, quote, text, tags, model,
                                   prompt_version, created_at, state, user_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                yap_id,
                f["type"],
                f["quote"],
                f["text"],
                json.dumps(f.get("tags", [])),
                model,
                prompt_version,
                created_at,
                state,
                user_text,
            ),
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


_FRAGMENT_STATES = {"active", "done", "archived", "deleted"}


def set_fragment_state(conn: sqlite3.Connection, frag_id: int, state: str) -> None:
    """User layer only — never touches the transcript or verbatim quote."""
    if state not in _FRAGMENT_STATES:
        raise ValueError(f"invalid fragment state: {state!r}")
    conn.execute("UPDATE fragments SET state = ? WHERE id = ?", (state, frag_id))
    conn.commit()


def set_fragment_text(
    conn: sqlite3.Connection, frag_id: int, user_text: str | None
) -> None:
    """Set (or clear, with None) the user-edited text. The LLM `text`, the
    verbatim `quote`, and the raw transcript are all left untouched."""
    conn.execute(
        "UPDATE fragments SET user_text = ? WHERE id = ?", (user_text, frag_id)
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
