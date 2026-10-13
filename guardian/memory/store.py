"""
Guardian Memory Store
=====================
SQLite-backed persistence layer for all Guardian memory types.

Constitution reference: Section 8 (Memory), Section 11 (Transparency),
Section 13 (Failure Policy).

Design rules:
  - Every write is logged
  - Schema is minimal and forward-compatible (ALTER TABLE for new columns)
  - In-memory mode (:memory:) used for tests — no temp files
  - File mode creates parent directories automatically
  - close() is idempotent and safe to call multiple times

Tables:
  episodic  — past conversation turns (who said what, when, which model)
  semantic  — user-approved facts and preferences (key-value)

Permissions: Level 1 — writes files within workspace boundary
Failure:    DB errors logged and re-raised as MemoryError
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from guardian.logging.logger import get_logger

log = get_logger(__name__)


class MemoryError(Exception):
    """Raised when a memory store operation fails."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS episodic (
    id            TEXT    PRIMARY KEY,
    session_id    TEXT    NOT NULL,
    turn_number   INTEGER NOT NULL,
    user_message  TEXT    NOT NULL,
    assistant_reply TEXT  NOT NULL,
    model_provider TEXT   DEFAULT '',
    model_name    TEXT    DEFAULT '',
    tokens_used   INTEGER DEFAULT 0,
    duration_ms   REAL    DEFAULT 0.0,
    timestamp     TEXT    NOT NULL,
    tags          TEXT    DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS semantic (
    key       TEXT  PRIMARY KEY,
    value     TEXT  NOT NULL,
    category  TEXT  DEFAULT 'general',
    source    TEXT  DEFAULT 'user',
    timestamp TEXT  NOT NULL,
    notes     TEXT  DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_episodic_ts      ON episodic(timestamp);
CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id);
CREATE INDEX IF NOT EXISTS idx_semantic_cat     ON semantic(category);
"""


class MemoryStore:
    """
    SQLite connection wrapper and schema manager.

    Usage:
        store = MemoryStore(db_path)   # real file
        store = MemoryStore(":memory:") # in-process, for tests
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        log.debug(f"MemoryStore initialised: {self._db_path}")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self) -> None:
        try:
            conn = self._get_conn()
            conn.executescript(SCHEMA)
            conn.commit()
        except sqlite3.Error as exc:
            raise MemoryError(f"Schema init failed: {exc}") from exc

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        try:
            conn = self._get_conn()
            cur = conn.execute(sql, params)
            conn.commit()
            return cur
        except sqlite3.Error as exc:
            raise MemoryError(f"DB error: {exc}") from exc

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        try:
            cur = self._get_conn().execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            raise MemoryError(f"DB query error: {exc}") from exc

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            log.debug("MemoryStore connection closed")

    def path(self) -> str:
        return self._db_path
