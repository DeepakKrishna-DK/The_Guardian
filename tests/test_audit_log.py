"""
Tests for guardian.audit — M2 Audit Log
=========================================
All tests use tmp_path; no test touches the production data directory.
Apache-2.0.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from guardian.audit.log import _GENESIS_HASH, AuditLog, _canonical_json, _sha256, get_data_dir

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_log(tmp_path: Path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.db")


# ── Basic append / verify ─────────────────────────────────────────────────────

class TestAppendAndVerify:
    def test_empty_chain_is_valid(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        ok, checked, bad_seq, reason = log.verify_chain()
        assert ok
        assert checked == 0
        assert bad_seq is None
        assert reason is None

    def test_single_event_verifies(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        seq = log.append("test.event", actor="unittest")
        assert seq == 1
        ok, checked, bad_seq, reason = log.verify_chain()
        assert ok, reason
        assert checked == 1

    def test_multiple_events_verify(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        for i in range(10):
            log.append("test.event", actor="u", payload={"i": i})
        ok, checked, bad_seq, _ = log.verify_chain()
        assert ok
        assert checked == 10

    def test_first_event_uses_genesis_hash(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        log.append("test.event")
        events = list(log.iter_events())
        assert events[0]["prev_hash"] == _GENESIS_HASH

    def test_hash_chain_links(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        log.append("ev.one")
        log.append("ev.two")
        events = list(log.iter_events())
        assert events[1]["prev_hash"] == events[0]["hash"]


# ── Persistence across reopen ─────────────────────────────────────────────────

class TestPersistence:
    def test_chain_continues_after_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log1 = AuditLog(path=db_path)
        log1.append("session.start")
        log1.append("model.call")
        log1.close()

        log2 = AuditLog(path=db_path)
        log2.append("session.end")
        ok, checked, bad_seq, reason = log2.verify_chain()
        assert ok, reason
        assert checked == 3

    def test_seq_continues_after_reopen(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log1 = AuditLog(path=db_path)
        log1.append("e1")
        log1.close()

        log2 = AuditLog(path=db_path)
        seq = log2.append("e2")
        assert seq == 2


# ── Append-only enforcement ───────────────────────────────────────────────────

class TestAppendOnly:
    def test_update_blocked(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        log.append("test.event")
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError), match="append-only"):
            log._conn.execute("UPDATE audit_events SET event_type='evil' WHERE seq=1")

    def test_delete_blocked(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        log.append("test.event")
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError), match="append-only"):
            log._conn.execute("DELETE FROM audit_events WHERE seq=1")


# ── Tamper detection ─────────────────────────────────────────────────────────

class TestTamperDetection:
    def test_tamper_detected_after_trigger_drop(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)
        log.append("ev.one")
        log.append("ev.two")
        log.close()

        # Drop the trigger and tamper row 1
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TRIGGER IF EXISTS audit_no_update")
        conn.execute("UPDATE audit_events SET event_type='evil' WHERE seq=1")
        conn.commit()
        conn.close()

        log2 = AuditLog(path=db_path)
        ok, checked, bad_seq, reason = log2.verify_chain()
        assert not ok
        assert bad_seq == 1
        assert reason is not None

    def test_tamper_row2_detected(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)
        for i in range(5):
            log.append("ev", payload={"i": i})
        log.close()

        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TRIGGER IF EXISTS audit_no_update")
        conn.execute("UPDATE audit_events SET actor='evil' WHERE seq=3")
        conn.commit()
        conn.close()

        log2 = AuditLog(path=db_path)
        ok, checked, bad_seq, reason = log2.verify_chain()
        assert not ok
        assert bad_seq == 3

    def test_seq_gap_detected(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)
        for _ in range(5):
            log.append("ev")
        log.close()

        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TRIGGER IF EXISTS audit_no_delete")
        conn.execute("DELETE FROM audit_events WHERE seq=3")
        conn.commit()
        conn.close()

        log2 = AuditLog(path=db_path)
        ok, checked, bad_seq, reason = log2.verify_chain()
        assert not ok
        assert reason is not None and ("gap" in reason or "mismatch" in reason or bad_seq is not None)


# ── Concurrent appends ────────────────────────────────────────────────────────

class TestConcurrency:
    def test_concurrent_appends_keep_chain_valid(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        errors: list[Exception] = []

        def worker(n: int) -> None:
            try:
                for i in range(10):
                    log.append("thread.event", actor=f"t{n}", payload={"i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        ok, checked, bad_seq, reason = log.verify_chain()
        assert ok, reason
        assert checked == 50


# ── Secret redaction ─────────────────────────────────────────────────────────

class TestRedaction:
    def test_no_secret_in_db_bytes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "audit.db"
        log = AuditLog(path=db_path)
        fake_key = "gsk_" + "A" * 45  # matches guardrails SECRET_LEAK pattern
        log.append("test.event", payload={"key": fake_key})
        log.close()

        raw_bytes = db_path.read_bytes()
        # The raw secret must not appear in the DB file
        assert fake_key.encode() not in raw_bytes

    def test_redacted_payload_stored(self, tmp_path: Path) -> None:
        log = make_log(tmp_path)
        fake_key = "gsk_" + "B" * 45
        log.append("test.event", payload={"apikey": fake_key})
        events = list(log.iter_events())
        assert fake_key not in json.dumps(events[0]["payload"])


# ── Default path ─────────────────────────────────────────────────────────────

class TestDefaultPath:
    def test_default_path_outside_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARDIAN_DATA_DIR", str(tmp_path / "data"))
        data_dir = get_data_dir()
        # Must not be inside the repo (repo root contains guardian/ package)
        repo_root = Path(__file__).resolve().parent.parent
        try:
            data_dir.resolve().relative_to(repo_root)
            inside_repo = True
        except ValueError:
            inside_repo = False
        assert not inside_repo, f"Default data dir {data_dir} is inside the repo"

    def test_env_override_respected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARDIAN_DATA_DIR", str(tmp_path / "custom"))
        log = AuditLog()  # uses GUARDIAN_DATA_DIR
        log.append("test.event")
        ok, checked, _, _ = log.verify_chain()
        assert ok
        assert checked == 1
        log.close()
