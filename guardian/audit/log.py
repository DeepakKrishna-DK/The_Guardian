"""
Guardian Audit Log — guardian/audit/log.py
============================================
Append-only, hash-chained SQLite audit log.

Design decisions:
  - Each event is linked to the previous via SHA-256 hash chain
  - Genesis prev_hash = '0' * 64
  - hash = sha256(prev_hash || canonical_json(fields))
  - canonical_json: sort_keys=True, separators=(",",":"), ensure_ascii=True
  - PRAGMA synchronous=FULL for durability
  - SQLite triggers block UPDATE and DELETE (append-only enforcement)
  - Threading: one Lock per connection for thread safety
  - Payload redaction: secret patterns scrubbed before storage
  - Content policy: NO raw prompt/response text ever stored.
    Model calls stored as: {provider, model, locality, prompt_sha256,
    prompt_len, response_len, status, duration_ms}

ADR Note:
  tamper-EVIDENT, not tamper-PROOF. A full-chain rewrite or tail
  truncation is possible. Future: anchor head hash externally (e.g.
  public ledger or signed HSM log).

Apache-2.0. SQLite is public domain.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from guardian.audit.redact import redact_payload

_GENESIS_HASH = "0" * 64

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,
    event_type   TEXT    NOT NULL,
    actor        TEXT    NOT NULL,
    session_id   TEXT    NOT NULL DEFAULT '',
    trace_id     TEXT,
    payload_json TEXT    NOT NULL DEFAULT '{}',
    prev_hash    TEXT    NOT NULL,
    hash         TEXT    NOT NULL
);
"""

# Append-only enforcement via SQLite triggers
_BLOCK_UPDATE = """
CREATE TRIGGER IF NOT EXISTS audit_no_update
    BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: UPDATE not allowed');
END;
"""

_BLOCK_DELETE = """
CREATE TRIGGER IF NOT EXISTS audit_no_delete
    BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: DELETE not allowed');
END;
"""


def _canonical_json(
    ts: str,
    event_type: str,
    actor: str,
    session_id: str,
    trace_id: str | None,
    payload: dict[str, Any],
) -> str:
    """Produce canonical JSON for hashing. Keys sorted, compact, ASCII-safe."""
    doc = {
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
        "session_id": session_id,
        "trace_id": trace_id,
        "ts": ts,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_data_dir() -> Path:
    """Return runtime data directory (outside repo). Override with GUARDIAN_DATA_DIR."""
    import os
    import sys

    env = os.environ.get("GUARDIAN_DATA_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return Path(base) / "Guardian"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "guardian"
    return Path.home() / ".local" / "share" / "guardian"


class AuditLog:
    """
    Append-only, hash-chained SQLite audit log.

    Usage:
        log = AuditLog(path=tmp_path / "audit.db")
        log.append("model.call", actor="guardian", payload={"provider": "groq"})
        ok, checked, bad_seq, reason = log.verify_chain()
    """

    def __init__(self, path: Path | str | None = None) -> None:
        if path is None:
            d = get_data_dir()
            d.mkdir(parents=True, exist_ok=True)
            path = d / "audit.db"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(_CREATE_TABLE + _BLOCK_UPDATE + _BLOCK_DELETE)
        self._conn.commit()

    # ── Public API ────────────────────────────────────────────────────────────

    def append(
        self,
        event_type: str,
        *,
        actor: str = "guardian",
        session_id: str = "",
        trace_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """
        Append one event. Thread-safe. Returns the assigned seq number.

        Payload is redacted (secrets scrubbed) before storage and hashing.
        Raw prompt/response text must NEVER be passed in payload.
        """
        raw_payload = payload or {}
        clean_payload = redact_payload(raw_payload)
        ts = _utc_now()

        with self._lock:
            with self._conn:
                self._conn.execute("BEGIN IMMEDIATE")
                prev_hash = self._get_last_hash()
                canonical = _canonical_json(ts, event_type, actor, session_id, trace_id, clean_payload)
                new_hash = _sha256(prev_hash + canonical)
                payload_json = json.dumps(clean_payload, ensure_ascii=True)

                cur = self._conn.execute(
                    """INSERT INTO audit_events
                       (ts, event_type, actor, session_id, trace_id,
                        payload_json, prev_hash, hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ts, event_type, actor, session_id, trace_id,
                     payload_json, prev_hash, new_hash),
                )
                return cur.lastrowid  # type: ignore[return-value]

    def verify_chain(self) -> tuple[bool, int, int | None, str | None]:
        """
        Verify the hash chain integrity.

        Returns:
            (ok, checked, first_bad_seq, reason)
            ok: True if chain is intact
            checked: number of events verified
            first_bad_seq: seq of first bad event (None if ok)
            reason: description of failure (None if ok)
        """
        rows = self._conn.execute(
            "SELECT seq, ts, event_type, actor, session_id, trace_id, "
            "payload_json, prev_hash, hash FROM audit_events ORDER BY seq"
        ).fetchall()

        if not rows:
            return (True, 0, None, None)

        prev_hash = _GENESIS_HASH
        expected_seq = rows[0][0]  # first seq

        for row in rows:
            seq, ts, event_type, actor, session_id, trace_id, payload_json, stored_prev, stored_hash = row

            # Check seq contiguity
            if seq != expected_seq:
                return (False, expected_seq - rows[0][0], seq, f"seq gap: expected {expected_seq}, got {seq}")

            # Check prev_hash linkage
            if stored_prev != prev_hash:
                return (False, seq - rows[0][0], seq, f"prev_hash mismatch at seq {seq}")

            # Recompute hash
            try:
                payload_dict = json.loads(payload_json)
            except json.JSONDecodeError:
                return (False, seq - rows[0][0], seq, f"invalid payload JSON at seq {seq}")

            canonical = _canonical_json(ts, event_type, actor, session_id, trace_id, payload_dict)
            expected_hash = _sha256(stored_prev + canonical)

            if stored_hash != expected_hash:
                return (False, seq - rows[0][0], seq, f"hash mismatch at seq {seq}")

            prev_hash = stored_hash
            expected_seq = seq + 1

        return (True, len(rows), None, None)

    def iter_events(self) -> Generator[dict[str, Any], None, None]:
        """Yield all events as dicts in seq order."""
        rows = self._conn.execute(
            "SELECT seq, ts, event_type, actor, session_id, trace_id, "
            "payload_json, prev_hash, hash FROM audit_events ORDER BY seq"
        ).fetchall()
        for row in rows:
            seq, ts, event_type, actor, session_id, trace_id, payload_json, prev_hash, hash_ = row
            yield {
                "seq": seq,
                "ts": ts,
                "event_type": event_type,
                "actor": actor,
                "session_id": session_id,
                "trace_id": trace_id,
                "payload": json.loads(payload_json),
                "prev_hash": prev_hash,
                "hash": hash_,
            }

    def close(self) -> None:
        self._conn.close()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_last_hash(self) -> str:
        """Get the hash of the last event. Returns genesis hash if empty."""
        row = self._conn.execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else _GENESIS_HASH


# ── Singleton for production use ──────────────────────────────────────────────

_default_log: AuditLog | None = None
_default_log_lock = threading.Lock()


def get_audit_log() -> AuditLog:
    """Return the process-wide AuditLog singleton (default path)."""
    global _default_log
    with _default_log_lock:
        if _default_log is None:
            _default_log = AuditLog()
    return _default_log


def reset_audit_log() -> None:
    """Reset singleton (for tests)."""
    global _default_log
    with _default_log_lock:
        if _default_log is not None:
            try:
                _default_log.close()
            except Exception:
                pass
        _default_log = None
