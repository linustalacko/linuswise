"""SQLite storage layer."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from .models import Highlight

SCHEMA = """
CREATE TABLE IF NOT EXISTS highlights (
    id              INTEGER PRIMARY KEY,
    hash            TEXT UNIQUE NOT NULL,
    text            TEXT NOT NULL,
    note            TEXT,
    source_title    TEXT NOT NULL,
    source_author   TEXT,
    source_type     TEXT NOT NULL DEFAULT 'kindle',
    location        TEXT,
    added_at        TEXT,
    created_at      TEXT NOT NULL,
    last_reviewed_at TEXT,
    review_count    INTEGER NOT NULL DEFAULT 0,
    favorite        INTEGER NOT NULL DEFAULT 0,
    discarded       INTEGER NOT NULL DEFAULT 0,
    embedding       BLOB,
    embedding_model TEXT
);
CREATE INDEX IF NOT EXISTS idx_highlights_review
    ON highlights (discarded, last_reviewed_at);

CREATE TABLE IF NOT EXISTS daily_review (
    day             TEXT NOT NULL,
    highlight_id    INTEGER NOT NULL,
    position        INTEGER NOT NULL,
    action          TEXT,                 -- keep | skip | discard | NULL (unseen)
    PRIMARY KEY (day, highlight_id)
);
"""

# Columns added after the first release; applied to pre-existing databases.
_MIGRATIONS = {
    "favorite": "ALTER TABLE highlights ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0",
    "embedding": "ALTER TABLE highlights ADD COLUMN embedding BLOB",
    "embedding_model": "ALTER TABLE highlights ADD COLUMN embedding_model TEXT",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def today_str() -> str:
    return date.today().isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(highlights)")}
    for col, ddl in _MIGRATIONS.items():
        if col not in cols:
            conn.execute(ddl)
    conn.commit()


def upsert(conn: sqlite3.Connection, highlights: list[Highlight]) -> tuple[int, int]:
    """Insert new highlights; fill in notes/locations on ones we already have.

    Returns (inserted, updated).
    """
    inserted = updated = 0
    for h in highlights:
        row = conn.execute(
            "SELECT id, note, location FROM highlights WHERE hash = ?", (h.hash(),)
        ).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO highlights
                   (hash, text, note, source_title, source_author, source_type, location, added_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    h.hash(),
                    h.text,
                    h.note,
                    h.source_title,
                    h.source_author,
                    h.source_type,
                    h.location,
                    h.added_at,
                    _now(),
                ),
            )
            inserted += 1
        else:
            new_note = h.note or row["note"]
            new_loc = h.location or row["location"]
            if new_note != row["note"] or new_loc != row["location"]:
                conn.execute(
                    "UPDATE highlights SET note = ?, location = ? WHERE id = ?",
                    (new_note, new_loc, row["id"]),
                )
                updated += 1
    conn.commit()
    return inserted, updated


# ---------------------------------------------------------------- review picks


def pick_for_review(conn: sqlite3.Connection, count: int, min_chars: int) -> list[sqlite3.Row]:
    """Spaced-repetition-ish selection, Readwise style.

    Surface highlights shown least recently, strongly favouring never-shown ones,
    with light randomness so the same set doesn't recur in lockstep.
    """
    return conn.execute(
        """SELECT * FROM highlights
           WHERE discarded = 0 AND length(trim(text)) >= ?
           ORDER BY (last_reviewed_at IS NOT NULL),
                    last_reviewed_at ASC,
                    random()
           LIMIT ?""",
        (min_chars, count),
    ).fetchall()


def mark_reviewed(conn: sqlite3.Connection, ids: list[int]) -> None:
    if not ids:
        return
    now = _now()
    conn.executemany(
        "UPDATE highlights SET last_reviewed_at = ?, review_count = review_count + 1 WHERE id = ?",
        [(now, i) for i in ids],
    )
    conn.commit()


# ---------------------------------------------------------------- daily batch


def get_or_create_today(conn: sqlite3.Connection, count: int, min_chars: int) -> list[sqlite3.Row]:
    """Return today's review set, creating (and persisting) it on first access.

    The daily email and the desktop UI share this one batch, so acting on a card
    in the app reflects the same highlights you were emailed.
    """
    day = today_str()
    existing = conn.execute(
        """SELECT h.*, d.position, d.action FROM daily_review d
           JOIN highlights h ON h.id = d.highlight_id
           WHERE d.day = ? ORDER BY d.position""",
        (day,),
    ).fetchall()
    if existing:
        return existing

    picks = pick_for_review(conn, count, min_chars)
    conn.executemany(
        "INSERT OR IGNORE INTO daily_review (day, highlight_id, position, action) VALUES (?, ?, ?, NULL)",
        [(day, r["id"], i) for i, r in enumerate(picks)],
    )
    mark_reviewed(conn, [r["id"] for r in picks])
    conn.commit()
    return conn.execute(
        """SELECT h.*, d.position, d.action FROM daily_review d
           JOIN highlights h ON h.id = d.highlight_id
           WHERE d.day = ? ORDER BY d.position""",
        (day,),
    ).fetchall()


def set_action(conn: sqlite3.Connection, highlight_id: int, action: str) -> None:
    """Record a review action and reflect it on the highlight.

    keep -> favorite; skip -> no-op flag; discard -> remove from rotation.
    """
    day = today_str()
    conn.execute(
        "UPDATE daily_review SET action = ? WHERE day = ? AND highlight_id = ?",
        (action, day, highlight_id),
    )
    if action == "keep":
        conn.execute("UPDATE highlights SET favorite = 1 WHERE id = ?", (highlight_id,))
    elif action == "discard":
        conn.execute("UPDATE highlights SET discarded = 1 WHERE id = ?", (highlight_id,))
    elif action == "skip":
        conn.execute("UPDATE highlights SET favorite = 0 WHERE id = ?", (highlight_id,))
    conn.commit()


# ---------------------------------------------------------------- queries


def all_highlights(
    conn: sqlite3.Connection, query: str = "", only_favorites: bool = False, limit: int = 500
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM highlights WHERE discarded = 0"
    params: list = []
    if query:
        sql += " AND (text LIKE ? OR source_title LIKE ? OR source_author LIKE ? OR note LIKE ?)"
        like = f"%{query}%"
        params += [like, like, like, like]
    if only_favorites:
        sql += " AND favorite = 1"
    sql += " ORDER BY COALESCE(added_at, created_at) DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM highlights WHERE discarded = 0").fetchone()[0]
    reviewed = conn.execute(
        "SELECT COUNT(*) FROM highlights WHERE discarded = 0 AND last_reviewed_at IS NOT NULL"
    ).fetchone()[0]
    favorites = conn.execute(
        "SELECT COUNT(*) FROM highlights WHERE discarded = 0 AND favorite = 1"
    ).fetchone()[0]
    embedded = conn.execute(
        "SELECT COUNT(*) FROM highlights WHERE embedding IS NOT NULL"
    ).fetchone()[0]
    by_type = dict(
        conn.execute(
            "SELECT source_type, COUNT(*) FROM highlights WHERE discarded = 0 GROUP BY source_type"
        ).fetchall()
    )
    books = conn.execute(
        "SELECT COUNT(DISTINCT source_title) FROM highlights WHERE discarded = 0"
    ).fetchone()[0]
    return {
        "total": total,
        "reviewed": reviewed,
        "never_reviewed": total - reviewed,
        "favorites": favorites,
        "embedded": embedded,
        "by_type": by_type,
        "books": books,
    }
