"""
Tests for Phase 4 — Memory System
===================================
All tests use MemoryStore(":memory:") — no files written to disk.
Tests are deterministic, isolated, and do NOT require API keys.

Covers:
  MemoryStore   — schema creation, execute, fetchall
  EpisodicMemory — save, list, search, delete, clear, count
  SemanticMemory — set, get, delete, clear, list, context prompt
  MemoryManager  — facade, build_system_prompt, status
"""

from __future__ import annotations

from datetime import datetime

import pytest

from guardian.memory import MemoryManager
from guardian.memory.episodic import EpisodicMemory, EpisodicRecord
from guardian.memory.semantic import VALID_CATEGORIES, SemanticFact, SemanticMemory
from guardian.memory.store import MemoryStore

# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore(":memory:")

@pytest.fixture
def episodic(store: MemoryStore) -> EpisodicMemory:
    return EpisodicMemory(store)

@pytest.fixture
def semantic(store: MemoryStore) -> SemanticMemory:
    return SemanticMemory(store)

@pytest.fixture
def manager(store: MemoryStore) -> MemoryManager:
    return MemoryManager(store)

def save_test_turn(em: EpisodicMemory, n: int = 1, session: str = "s1") -> str:
    return em.save_turn(
        session_id=session,
        turn_number=n,
        user_message=f"user question {n}",
        assistant_reply=f"guardian answer {n}",
        model_provider="mock",
        model_name="guardian-mock-v1",
        tokens_used=100 * n,
        duration_ms=50.0 * n,
    )


# ─── MemoryStore ─────────────────────────────────────────────────────────────

class TestMemoryStore:
    def test_creates_in_memory(self):
        s = MemoryStore(":memory:")
        assert s is not None

    def test_path_returns_db_path(self):
        s = MemoryStore(":memory:")
        assert s.path() == ":memory:"

    def test_execute_returns_cursor(self, store):
        cur = store.execute("SELECT 1")
        assert cur is not None

    def test_fetchall_returns_list(self, store):
        rows = store.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        assert isinstance(rows, list)

    def test_episodic_table_exists(self, store):
        rows = store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='episodic'"
        )
        assert len(rows) == 1

    def test_semantic_table_exists(self, store):
        rows = store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='semantic'"
        )
        assert len(rows) == 1

    def test_close_is_idempotent(self, store):
        store.close()
        store.close()  # Should not raise


# ─── EpisodicMemory ──────────────────────────────────────────────────────────

class TestEpisodicMemory:
    def test_save_returns_id(self, episodic):
        rid = save_test_turn(episodic)
        assert isinstance(rid, str)
        assert len(rid) == 36  # UUID format

    def test_count_increments_on_save(self, episodic):
        assert episodic.count() == 0
        save_test_turn(episodic, 1)
        assert episodic.count() == 1
        save_test_turn(episodic, 2)
        assert episodic.count() == 2

    def test_list_recent_returns_records(self, episodic):
        save_test_turn(episodic, 1)
        save_test_turn(episodic, 2)
        records = episodic.list_recent(10)
        assert len(records) == 2
        assert all(isinstance(r, EpisodicRecord) for r in records)

    def test_list_recent_newest_first(self, episodic):
        save_test_turn(episodic, 1)
        save_test_turn(episodic, 2)
        records = episodic.list_recent(10)
        # Newest (turn 2) should be first
        assert records[0].turn_number == 2
        assert records[1].turn_number == 1

    def test_list_recent_respects_limit(self, episodic):
        for i in range(5):
            save_test_turn(episodic, i + 1)
        records = episodic.list_recent(3)
        assert len(records) == 3

    def test_get_by_id(self, episodic):
        rid = save_test_turn(episodic, 1)
        record = episodic.get(rid)
        assert record is not None
        assert record.id == rid
        assert record.turn_number == 1

    def test_get_unknown_id_returns_none(self, episodic):
        assert episodic.get("nonexistent-id") is None

    def test_search_finds_by_user_message(self, episodic):
        em = episodic
        em.save_turn("s1", 1, "what is Python?", "Python is a language.", "mock", "m")
        em.save_turn("s1", 2, "what is Java?", "Java is compiled.", "mock", "m")
        results = em.search("Python")
        assert len(results) == 1
        assert "Python" in results[0].user_message

    def test_search_finds_by_assistant_reply(self, episodic):
        em = episodic
        em.save_turn("s1", 1, "tell me something", "Guardian is a personal AI.", "mock", "m")
        results = em.search("personal AI")
        assert len(results) == 1

    def test_search_case_insensitive(self, episodic):
        em = episodic
        em.save_turn("s1", 1, "UPPER CASE QUERY", "reply", "mock", "m")
        results = em.search("upper case")
        assert len(results) == 1

    def test_search_no_results(self, episodic):
        save_test_turn(episodic, 1)
        results = episodic.search("zzznomatch999")
        assert results == []

    def test_delete_removes_record(self, episodic):
        rid = save_test_turn(episodic)
        assert episodic.count() == 1
        deleted = episodic.delete(rid)
        assert deleted is True
        assert episodic.count() == 0

    def test_delete_returns_false_for_unknown(self, episodic):
        assert episodic.delete("no-such-id") is False

    def test_clear_removes_all(self, episodic):
        for i in range(5):
            save_test_turn(episodic, i + 1)
        count = episodic.clear()
        assert count == 5
        assert episodic.count() == 0

    def test_count_for_session(self, episodic):
        save_test_turn(episodic, 1, session="session_a")
        save_test_turn(episodic, 2, session="session_a")
        save_test_turn(episodic, 3, session="session_b")
        assert episodic.count_for_session("session_a") == 2
        assert episodic.count_for_session("session_b") == 1
        assert episodic.count_for_session("session_c") == 0

    def test_record_preview(self, episodic):
        rid = save_test_turn(episodic, 1)
        record = episodic.get(rid)
        preview = record.preview()
        assert isinstance(preview, str)
        assert "user question 1" in preview

    def test_record_timestamp_is_datetime(self, episodic):
        rid = save_test_turn(episodic, 1)
        record = episodic.get(rid)
        assert isinstance(record.timestamp, datetime)

    def test_stores_model_info(self, episodic):
        rid = save_test_turn(episodic, 1)
        record = episodic.get(rid)
        assert record.model_provider == "mock"
        assert record.model_name == "guardian-mock-v1"
        assert record.tokens_used == 100
        assert record.duration_ms == 50.0


# ─── SemanticMemory ──────────────────────────────────────────────────────────

class TestSemanticMemory:
    def test_set_and_get(self, semantic):
        semantic.set("name", "Alice")
        assert semantic.get("name") == "Alice"

    def test_get_unknown_returns_none(self, semantic):
        assert semantic.get("nonexistent") is None

    def test_set_overwrites_existing(self, semantic):
        semantic.set("lang", "Python")
        semantic.set("lang", "Rust")
        assert semantic.get("lang") == "Rust"

    def test_key_is_case_insensitive(self, semantic):
        semantic.set("MyKey", "value")
        assert semantic.get("mykey") == "value"
        assert semantic.get("MYKEY") == "value"
        assert semantic.get("MyKey") == "value"

    def test_empty_key_raises(self, semantic):
        with pytest.raises(ValueError, match="key must not be empty"):
            semantic.set("", "value")

    def test_empty_value_raises(self, semantic):
        with pytest.raises(ValueError, match="value must not be empty"):
            semantic.set("key", "")

    def test_invalid_category_raises(self, semantic):
        with pytest.raises(ValueError, match="Category must be one of"):
            semantic.set("k", "v", category="invalid_category")

    def test_valid_categories(self, semantic):
        for cat in VALID_CATEGORIES:
            semantic.set(f"test_{cat}", "val", category=cat)

    def test_delete_removes_fact(self, semantic):
        semantic.set("to_delete", "gone")
        assert semantic.delete("to_delete") is True
        assert semantic.get("to_delete") is None

    def test_delete_returns_false_for_unknown(self, semantic):
        assert semantic.delete("nonexistent") is False

    def test_count(self, semantic):
        assert semantic.count() == 0
        semantic.set("a", "1")
        semantic.set("b", "2")
        assert semantic.count() == 2

    def test_list_all_returns_all(self, semantic):
        semantic.set("x", "1", category="fact")
        semantic.set("y", "2", category="preference")
        facts = semantic.list_all()
        assert len(facts) == 2
        assert all(isinstance(f, SemanticFact) for f in facts)

    def test_list_all_filtered_by_category(self, semantic):
        semantic.set("a", "1", category="preference")
        semantic.set("b", "2", category="fact")
        semantic.set("c", "3", category="preference")
        prefs = semantic.list_all(category="preference")
        assert len(prefs) == 2
        assert all(f.category == "preference" for f in prefs)

    def test_clear_removes_all(self, semantic):
        semantic.set("a", "1")
        semantic.set("b", "2")
        count = semantic.clear()
        assert count == 2
        assert semantic.count() == 0

    def test_clear_by_category(self, semantic):
        semantic.set("a", "1", category="preference")
        semantic.set("b", "2", category="fact")
        semantic.clear(category="preference")
        assert semantic.count() == 1
        assert semantic.get("b") == "2"

    def test_to_context_prompt_empty(self, semantic):
        assert semantic.to_context_prompt() == ""

    def test_to_context_prompt_with_facts(self, semantic):
        semantic.set("name", "Alice", category="preference")
        semantic.set("lang", "Python", category="preference")
        prompt = semantic.to_context_prompt()
        assert "User preferences and known facts:" in prompt
        assert "name: Alice" in prompt
        assert "lang: Python" in prompt

    def test_fact_timestamp_is_datetime(self, semantic):
        semantic.set("ts_test", "value")
        fact = semantic.get_fact("ts_test")
        assert isinstance(fact.timestamp, datetime)


# ─── MemoryManager ───────────────────────────────────────────────────────────

class TestMemoryManager:
    def test_has_episodic_and_semantic(self, manager):
        assert hasattr(manager, "episodic")
        assert hasattr(manager, "semantic")

    def test_status_returns_dict(self, manager):
        s = manager.status()
        assert isinstance(s, dict)
        assert "episodic_count" in s
        assert "semantic_count" in s
        assert "db_path" in s

    def test_status_counts_are_correct(self, manager):
        save_test_turn(manager.episodic)
        manager.semantic.set("k", "v")
        s = manager.status()
        assert s["episodic_count"] == 1
        assert s["semantic_count"] == 1

    def test_build_system_prompt_no_facts(self, manager):
        base = "You are Guardian."
        result = manager.build_system_prompt(base)
        assert result == base  # unchanged when no facts

    def test_build_system_prompt_with_facts(self, manager):
        manager.semantic.set("name", "Alice")
        base = "You are Guardian."
        result = manager.build_system_prompt(base)
        assert base in result
        assert "Alice" in result

    def test_close_is_safe(self, manager):
        manager.close()  # Should not raise
