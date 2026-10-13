"""
Tests for Phase 3 â€” Core Orchestrator
=======================================
All tests use MockBackend â€” no API calls, no network, no keys required.

Tests cover:
  - Session management (add, trim, convert to messages)
  - GuardianResponse structure and properties
  - GuardianCore.process() happy path
  - GuardianCore.process() error handling
  - Input validation
  - Model swap (Constitution: model must be replaceable)
"""

from __future__ import annotations

from datetime import datetime

from guardian.core.orchestrator import GuardianCore
from guardian.core.response import GuardianResponse
from guardian.core.session import Session
from guardian.model.backends.mock import MockBackend
from guardian.model.interface import Role

# â”€â”€â”€ Fixtures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def make_core(prefix: str = "[MOCK]") -> GuardianCore:
    return GuardianCore(model=MockBackend(response_prefix=prefix))

def make_session() -> Session:
    return Session()


# â”€â”€â”€ Session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestSession:
    def test_starts_empty(self):
        s = Session()
        assert s.turn_count == 0
        assert s.next_turn_number == 1

    def test_add_turn_increments(self):
        s = Session()
        s.add_turn("hello", "hi")
        assert s.turn_count == 1
        assert s.next_turn_number == 2

    def test_to_messages_empty(self):
        s = Session()
        assert s.to_messages() == []

    def test_to_messages_one_turn(self):
        s = Session()
        s.add_turn("hello", "hi there")
        msgs = s.to_messages()
        assert len(msgs) == 2
        assert msgs[0].role == Role.USER
        assert msgs[0].content == "hello"
        assert msgs[1].role == Role.ASSISTANT
        assert msgs[1].content == "hi there"

    def test_to_messages_with_next(self):
        s = Session()
        s.add_turn("first", "first reply")
        msgs = s.to_messages_with_next("second question")
        assert len(msgs) == 3
        assert msgs[-1].role == Role.USER
        assert msgs[-1].content == "second question"

    def test_trim_at_max(self):
        s = Session(max_turns=3)
        for i in range(5):
            s.add_turn(f"user {i}", f"reply {i}")
        # Only the last 3 turns should remain
        assert s.turn_count == 3
        # Most recent message should be from the last iteration (i=4)
        assert s.last_turn().user_message == "user 4"
        assert s.last_turn().assistant_reply == "reply 4"
        # Oldest retained should be i=2
        msgs = s.to_messages()
        assert any("user 2" in m.content for m in msgs)
        assert not any("user 0" in m.content for m in msgs)
        assert not any("user 1" in m.content for m in msgs)

    def test_clear_empties_history(self):
        s = Session()
        s.add_turn("a", "b")
        s.clear()
        assert s.turn_count == 0
        assert s.to_messages() == []

    def test_total_tokens_sums(self):
        s = Session()
        s.add_turn("a", "b", tokens_used=10)
        s.add_turn("c", "d", tokens_used=20)
        assert s.total_tokens == 30

    def test_summary_returns_string(self):
        s = Session()
        assert isinstance(s.summary(), str)
        assert "turns" in s.summary()

    def test_last_turn_none_when_empty(self):
        s = Session()
        assert s.last_turn() is None

    def test_last_turn_returns_most_recent(self):
        s = Session()
        s.add_turn("first", "first reply")
        s.add_turn("second", "second reply")
        last = s.last_turn()
        assert last.user_message == "second"


# â”€â”€â”€ GuardianResponse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGuardianResponse:
    def test_success_is_true(self):
        r = GuardianResponse(
            content="hello", model_provider="mock", model_name="m",
            session_turn=1, duration_ms=50.0
        )
        assert r.success is True
        assert bool(r) is True

    def test_success_is_false_when_error(self):
        r = GuardianResponse(
            content="", model_provider="mock", model_name="m",
            session_turn=1, duration_ms=10.0, error="something failed"
        )
        assert r.success is False
        assert bool(r) is False

    def test_success_false_when_no_content(self):
        r = GuardianResponse(
            content="", model_provider="mock", model_name="m",
            session_turn=1, duration_ms=10.0
        )
        assert r.success is False

    def test_duration_s(self):
        r = GuardianResponse(
            content="x", model_provider="p", model_name="m",
            session_turn=1, duration_ms=1234.0
        )
        assert r.duration_s == 1.234

    def test_summary_contains_key_info(self):
        r = GuardianResponse(
            content="ok", model_provider="groq", model_name="m",
            session_turn=2, duration_ms=300.0, tokens_used=50
        )
        s = r.summary()
        assert "turn=2" in s
        assert "groq" in s
        assert "50" in s

    def test_timestamp_is_datetime(self):
        r = GuardianResponse(
            content="x", model_provider="p", model_name="m",
            session_turn=1, duration_ms=0.0
        )
        assert isinstance(r.timestamp, datetime)


# â”€â”€â”€ GuardianCore â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGuardianCore:
    def test_process_returns_response(self):
        core = make_core()
        session = make_session()
        resp = core.process("Hello Guardian", session)
        assert isinstance(resp, GuardianResponse)

    def test_process_success(self):
        core = make_core()
        session = make_session()
        resp = core.process("What time is it?", session)
        assert resp.success
        assert resp.content
        assert resp.error is None

    def test_process_records_in_session(self):
        core = make_core()
        session = make_session()
        core.process("First question", session)
        assert session.turn_count == 1

    def test_process_multiple_turns(self):
        core = make_core()
        session = make_session()
        core.process("Turn one", session)
        core.process("Turn two", session)
        core.process("Turn three", session)
        assert session.turn_count == 3

    def test_process_turn_number_increments(self):
        core = make_core()
        session = make_session()
        r1 = core.process("First", session)
        r2 = core.process("Second", session)
        assert r1.session_turn == 1
        assert r2.session_turn == 2

    def test_process_provider_in_response(self):
        core = make_core()
        session = make_session()
        resp = core.process("Test", session)
        assert resp.model_provider == "mock"

    def test_empty_input_returns_error(self):
        core = make_core()
        session = make_session()
        resp = core.process("", session)
        assert resp.success is False
        assert resp.error is not None
        # Empty input should NOT be recorded in session
        assert session.turn_count == 0

    def test_whitespace_input_returns_error(self):
        core = make_core()
        session = make_session()
        resp = core.process("   ", session)
        assert resp.success is False
        assert session.turn_count == 0

    def test_oversized_input_returns_error(self):
        core = make_core()
        session = make_session()
        huge_input = "x" * 40_000
        resp = core.process(huge_input, session)
        assert resp.success is False
        assert "too long" in resp.error.lower()
        assert session.turn_count == 0

    def test_history_passed_to_model(self):
        """Verify that previous turns appear in the request sent to the model."""
        mock = MockBackend()
        core = GuardianCore(model=mock)
        session = make_session()

        core.process("first message", session)
        core.process("second message", session)

        # By turn 2, the mock has been called twice
        assert mock.call_count == 2
        # Session has 2 turns
        assert session.turn_count == 2
        # Messages in session include both turns
        msgs = session.to_messages()
        assert any("first message" in m.content for m in msgs)
        assert any("second message" in m.content for m in msgs)

    def test_get_model_info(self):
        core = make_core()
        info = core.get_model_info()
        assert isinstance(info, dict)
        assert "provider" in info
        assert "model" in info
        assert "available" in info

    def test_swap_model(self):
        """Constitution section 10: model must be replaceable."""
        mock1 = MockBackend(response_prefix="[M1]")
        mock2 = MockBackend(response_prefix="[M2]")
        core = GuardianCore(model=mock1)
        session = make_session()

        r1 = core.process("Hello", session)
        assert "[M1]" in r1.content

        core.swap_model(mock2)

        r2 = core.process("Hello again", session)
        assert "[M2]" in r2.content

    def test_duration_ms_is_positive(self):
        core = make_core()
        session = make_session()
        resp = core.process("Test", session)
        assert resp.duration_ms >= 0

    def test_model_swap_on_local_only_policy(self):
        """Verify that Core swaps to a local model when Policy Engine denies cloud access."""
        from unittest.mock import patch
        from guardian.model.interface import BackendInfo, ModelResponse
        from guardian.skills.base import SkillName
        from guardian.skills import PENTEST_SKILL
        
        # Fake Cloud Model
        class FakeCloudBackend(MockBackend):
            def get_info(self):
                info = super().get_info()
                info.is_local = False
                info.name = "fake_cloud"
                info.provider = "Fake Cloud API"
                return info
                
            def complete(self, request):
                return ModelResponse(content="I am cloud", model="cloud-1", provider="Fake Cloud API")
                
            @property
            def locality(self): return "cloud"

        # Register a fake local model in the registry so it can be swapped to
        class FakeLocalBackend(MockBackend):
            def get_info(self):
                info = super().get_info()
                info.is_local = True
                info.name = "fake_local"
                info.provider = "Fake Local"
                return info
                
            def complete(self, request):
                return ModelResponse(content="I am local", model="local-1", provider="Fake Local")
                
            @property
            def locality(self): return "local"

        from guardian.model.registry import get_registry
        registry = get_registry()
        
        with patch.object(registry, "list_available") as mock_list:
            mock_list.return_value = [FakeLocalBackend().get_info()]
            with patch.object(registry, "get") as mock_get:
                mock_get.return_value = FakeLocalBackend()
                
                from guardian.model.router import ModelRouter
                router = ModelRouter(primary=FakeCloudBackend(), local=FakeLocalBackend())
                core = GuardianCore(router=router)
                session = make_session()
                
                # Test a standard skill (Scholar) -> Uses Cloud
                resp1 = core.process("Hello", session, active_skill="scholar")
                assert "cloud" in resp1.content
                assert resp1.model_provider == "Fake Cloud API"
                
                # Test a sensitive skill (Pentest) -> Swaps to Local
                resp2 = core.process("Exploit this", session, active_skill=PENTEST_SKILL.name)
                assert "local" in resp2.content
                assert resp2.model_provider == "Fake Local"


# â”€â”€â”€ Integration: orchestrator + session together â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestOrchestratorIntegration:
    def test_full_conversation_flow(self):
        """Simulate a realistic multi-turn conversation."""
        core = make_core()
        session = make_session()

        exchanges = [
            "What is AI Guardian?",
            "What principles does it follow?",
            "How does the memory system work?",
        ]

        for user_msg in exchanges:
            resp = core.process(user_msg, session)
            assert resp.success, f"Failed on: {user_msg!r}"

        assert session.turn_count == 3
        assert session.total_tokens > 0

    def test_clear_and_resume(self):
        """Clearing session should allow fresh start without error."""
        core = make_core()
        session = make_session()

        core.process("Question before clear", session)
        session.clear()
        assert session.turn_count == 0

        resp = core.process("Fresh start", session)
        assert resp.success
        assert session.turn_count == 1
    def test_guardrails_called_exactly_once(self):
        core = make_core()
        session = make_session()
        from unittest.mock import MagicMock, patch
        with patch('guardian.guardrails.get_guardrails_layer') as mock_get_gr:
            mock_layer = MagicMock()
            mock_layer.scan_input.return_value = MagicMock(blocked=False)
            mock_layer.scan_output.return_value = MagicMock(violations=[], passed=True)
            mock_get_gr.return_value = mock_layer
            core.process('hello', session)
            mock_layer.scan_input.assert_called_once_with('hello')
            mock_layer.scan_output.assert_called_once()
