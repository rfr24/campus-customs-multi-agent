"""Database access for the Campus Customs MCP server.

Every application read and write targets the *working copy*,
`data/campus_customs_new.db`. The original `data/campus_customs.db` is the
assignment's untouched reference and is never opened for writing here.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

ORIGINAL_DB = DATA_DIR / "campus_customs.db"

# Overridable so tests can point the whole stack at a disposable copy without
# touching the real working database. Unset in normal operation.
WORKING_DB = Path(os.environ.get("CAMPUS_CUSTOMS_DB_PATH", DATA_DIR / "campus_customs_new.db"))

# Operational caps so a tool can never return an unbounded result set.
MAX_ROWS = 200
DEFAULT_LIMIT = 50


class DatabaseError(RuntimeError):
    """Raised when the working database is missing or unusable."""


def _require_working_db() -> Path:
    if not WORKING_DB.is_file():
        raise DatabaseError(
            f"Working database not found at {WORKING_DB}. "
            "Run Problem 2 setup to create it from the original."
        )
    return WORKING_DB


def clamp_limit(limit: int | None) -> int:
    """Keep every list tool inside MAX_ROWS."""
    if limit is None:
        return DEFAULT_LIMIT
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(value, MAX_ROWS))


@contextmanager
def read_conn() -> Iterator[sqlite3.Connection]:
    """Read-only connection to the working copy.

    Opened through a `mode=ro` URI so a programming mistake in a read tool
    cannot write to the database at all.
    """
    path = _require_working_db()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write_conn() -> Iterator[sqlite3.Connection]:
    """Read/write connection to the working copy, with an atomic transaction.

    Foreign keys are enforced. The whole block commits together or rolls back
    together, so a payment row and the balance it draws down can never diverge.
    """
    path = _require_working_db()
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def shop_today(conn: sqlite3.Connection) -> str:
    """The shop's authoritative date, never the host clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise DatabaseError("desk table has no row; shop date is unknown.")
    return row["date_today"]
