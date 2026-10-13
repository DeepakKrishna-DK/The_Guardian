"""
Tests for Phase 2 — Model Abstraction Layer
============================================
These tests exercise the interface, data structures, registry,
and MockBackend without requiring any API key or network access.

Groq/Gemini backend tests only check structural behaviour
(is_available=False when no key) — NOT actual API calls.
Live API tests require keys and are explicitly skipped here.
"""

from __future__ import annotations

import os

import pytest

from guardian.model.backends.gemini_backend import GeminiBackend
from guardian.model.backends.groq_backend import GroqBackend
from guardian.model.backends.mock import MockBackend
from guardian.model.interface import (
    BackendInfo,
    Message,
    ModelRequest,
    ModelResponse,
    ModelUnavailableError,
    Role,
    TokenUsage,
)
from guardian.model.registry import ModelRegistry, get_registry

# ─── Message ─────────────────────────────────────────────────────────────────

class TestMessage:
    def test_user_factory(self):
        m = Message.user("hello")
        assert m.role == Role.USER
        assert m.content == "hello"

    def test_system_factory(self):
        m = Message.system("you are guardian")
        assert m.role == Role.SYSTEM

    def test_assistant_factory(self):
        m = Message.assistant("I can help")
        assert m.role == Role.ASSISTANT

    def test_to_dict(self):
        m = Message.user("test")
        d = m.to_dict()
        assert d == {"role": "user", "content": "test"}


# ─── ModelRequest ─────────────────────────────────────────────────────────────

class TestModelRequest:
    def test_basic_creation(self):
        req = ModelRequest(messages=[Message.user("hello")])
        assert len(req.messages) == 1
        assert req.max_tokens == 1024
        assert req.temperature == 0.7

    def test_empty_messages_raises(self):
        with pytest.raises(ValueError, match="at least one message"):
            ModelRequest(messages=[])

    def test_bad_temperature_raises(self):
        with pytest.raises(ValueError, match="temperature"):
            ModelRequest(messages=[Message.user("x")], temperature=3.0)

    def test_bad_max_tokens_raises(self):
        with pytest.raises(ValueError, match="max_tokens"):
            ModelRequest(messages=[Message.user("x")], max_tokens=0)

    def test_all_messages_no_system(self):
        req = ModelRequest(messages=[Message.user("hi")])
        msgs = req.all_messages()
        assert len(msgs) == 1
        assert msgs[0].role == Role.USER

    def test_all_messages_with_system(self):
        req = ModelRequest(
            messages=[Message.user("hi")],
            system_prompt="Be helpful"
        )
        msgs = req.all_messages()
        assert len(msgs) == 2
        assert msgs[0].role == Role.SYSTEM
        assert msgs[0].content == "Be helpful"
        assert msgs[1].role == Role.USER

    def test_metadata_default_empty(self):
        req = ModelRequest(messages=[Message.user("x")])
        assert req.metadata == {}


# ─── ModelResponse ────────────────────────────────────────────────────────────

class TestModelResponse:
    def test_basic(self):
        r = ModelResponse(content="hello", model="m1", provider="test")
        assert r.content == "hello"
        assert bool(r) is True

    def test_empty_content_is_falsy(self):
        r = ModelResponse(content="", model="m1", provider="test")
        assert bool(r) is False

    def test_usage_defaults(self):
        r = ModelResponse(content="x", model="m", provider="p")
        assert r.usage.total_tokens == 0


# ─── TokenUsage ───────────────────────────────────────────────────────────────

class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_set_values(self):
        u = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert u.total_tokens == 30


# ─── MockBackend ─────────────────────────────────────────────────────────────

class TestMockBackend:
    def test_always_available(self):
        m = MockBackend()
        assert m.is_available() is True

    def test_complete_returns_response(self):
        m = MockBackend()
        req = ModelRequest(messages=[Message.user("test input")])
        resp = m.complete(req)
        assert isinstance(resp, ModelResponse)
        assert resp.content
        assert resp.provider == "mock"

    def test_complete_echoes_user_content(self):
        m = MockBackend()
        req = ModelRequest(messages=[Message.user("unique phrase abc123")])
        resp = m.complete(req)
        assert "unique phrase abc123" in resp.content

    def test_call_count_increments(self):
        m = MockBackend()
        req = ModelRequest(messages=[Message.user("x")])
        m.complete(req)
        m.complete(req)
        assert m.call_count == 2

    def test_reset_clears_count(self):
        m = MockBackend()
        req = ModelRequest(messages=[Message.user("x")])
        m.complete(req)
        m.reset()
        assert m.call_count == 0

    def test_custom_prefix(self):
        m = MockBackend(response_prefix="[TEST]")
        req = ModelRequest(messages=[Message.user("hello")])
        resp = m.complete(req)
        assert resp.content.startswith("[TEST]")

    def test_get_info_shape(self):
        m = MockBackend()
        info = m.get_info()
        assert isinstance(info, BackendInfo)
        assert info.is_local is True
        assert info.requires_key is False
        assert info.available is True

    def test_usage_reported(self):
        m = MockBackend()
        req = ModelRequest(messages=[Message.user("hello world")])
        resp = m.complete(req)
        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0

    def test_with_system_prompt(self):
        m = MockBackend()
        req = ModelRequest(
            messages=[Message.user("question")],
            system_prompt="You are a guardian"
        )
        resp = m.complete(req)
        assert resp.content  # Should not crash with system prompt


# ─── GroqBackend (no key — structural tests only) ────────────────────────────

class TestGroqBackendNoKey:
    def setup_method(self):
        """Remove Groq key from env for these tests."""
        self._original = os.environ.pop("GUARDIAN_GROQ_API_KEY", None)

    def teardown_method(self):
        """Restore original key if present."""
        if self._original is not None:
            os.environ["GUARDIAN_GROQ_API_KEY"] = self._original

    def test_unavailable_without_key(self):
        b = GroqBackend()
        assert b.is_available() is False

    def test_get_info_when_unavailable(self):
        b = GroqBackend()
        info = b.get_info()
        assert info.available is False
        assert info.requires_key is True
        assert info.is_local is False
        assert "GUARDIAN_GROQ_API_KEY" in info.notes

    def test_complete_raises_without_key(self):
        b = GroqBackend()
        req = ModelRequest(messages=[Message.user("hello")])
        with pytest.raises(ModelUnavailableError):
            b.complete(req)

    def test_repr_shows_unavailable(self):
        b = GroqBackend()
        assert "unavailable" in repr(b).lower()


# ─── GeminiBackend (no key — structural tests only) ──────────────────────────

class TestGeminiBackendNoKey:
    def setup_method(self):
        self._original = os.environ.pop("GUARDIAN_GOOGLE_API_KEY", None)

    def teardown_method(self):
        if self._original is not None:
            os.environ["GUARDIAN_GOOGLE_API_KEY"] = self._original

    def test_unavailable_without_key(self):
        b = GeminiBackend()
        assert b.is_available() is False

    def test_get_info_when_unavailable(self):
        b = GeminiBackend()
        info = b.get_info()
        assert info.available is False
        assert info.requires_key is True
        assert info.is_local is False
        assert "GUARDIAN_GOOGLE_API_KEY" in info.notes

    def test_complete_raises_without_key(self):
        b = GeminiBackend()
        req = ModelRequest(messages=[Message.user("hello")])
        with pytest.raises(ModelUnavailableError):
            b.complete(req)


# ─── ModelRegistry ───────────────────────────────────────────────────────────

class TestModelRegistry:
    def test_register_and_get(self):
        reg = ModelRegistry()
        reg.register("mock", MockBackend)
        backend = reg.get("mock")
        assert isinstance(backend, MockBackend)

    def test_get_unknown_raises(self):
        reg = ModelRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_all_returns_infos(self):
        reg = ModelRegistry()
        reg.register("mock", MockBackend)
        infos = reg.list_all()
        assert len(infos) == 1
        assert infos[0].name == "mock"

    def test_get_available_returns_mock_when_only_option(self):
        reg = ModelRegistry()
        reg.register("mock", MockBackend)
        backend = reg.get_available()
        assert isinstance(backend, MockBackend)

    def test_get_available_prefers_named(self):
        reg = ModelRegistry()
        reg.register("mock", MockBackend)
        backend = reg.get_available(prefer="mock")
        assert isinstance(backend, MockBackend)

    def test_get_available_raises_when_empty(self):
        reg = ModelRegistry()
        with pytest.raises(ModelUnavailableError):
            reg.get_available()

    def test_list_available_filters(self):
        """Only backends that report is_available()=True appear in list_available()."""
        reg = ModelRegistry()
        reg.register("mock", MockBackend)
        available = reg.list_available()
        names = [i.name for i in available]
        assert "mock" in names
        # All listed backends must actually be available
        all_infos = reg.list_all()
        for info in all_infos:
            if info.available:
                assert info.name in names
            else:
                assert info.name not in names


# ─── Default registry ─────────────────────────────────────────────────────────

class TestDefaultRegistry:
    def test_registry_has_backends(self):
        reg = get_registry()
        infos = reg.list_all()
        assert len(infos) >= 1  # At least mock

    def test_mock_always_registered(self):
        reg = get_registry()
        names = [i.name for i in reg.list_all()]
        assert "mock" in names

    def test_groq_registered_and_has_info(self):
        """Groq must be registered and return valid BackendInfo."""
        reg = get_registry()
        names = [i.name for i in reg.list_all()]
        assert "groq" in names
        groq_info = next(i for i in reg.list_all() if i.name == "groq")
        # Structural checks — availability depends on environment
        assert groq_info.requires_key is True
        assert groq_info.is_local is False
        assert groq_info.provider == "Groq API"
        assert groq_info.model  # must have a model name
        # availability is honest: if key set, should be True; if not, False
        import os
        key_set = bool(os.environ.get("GUARDIAN_GROQ_API_KEY", "").strip())
        assert groq_info.available == key_set, (
            f"Groq availability={groq_info.available} but key_set={key_set}"
        )
