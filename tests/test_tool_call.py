"""
Tests for Phase 7 — Tool Call Parser and Tool Loop
=====================================================
All tests are deterministic and require no API calls.
MockBackend is used for all model interactions.

Covers:
  ToolCall dataclass
  parse_tool_calls: valid block, malformed JSON, missing name, multiple calls, no calls
  build_tool_result_message
  Session.add_raw_assistant_message / to_messages / clear
  ToolLoop: no tool calls (direct path), auto-run level-0, denied level-2,
            unknown tool, max rounds safety limit, multi-round
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardian.core.orchestrator import GuardianCore
from guardian.core.session import Session
from guardian.model.backends.mock import MockBackend
from guardian.model.interface import Role
from guardian.tools import reset_tool_executor
from guardian.tools.executor import ToolExecutor
from guardian.tools.file_read import FileReadTool
from guardian.tools.loop import MAX_TOOL_ROUNDS, ToolLoop
from guardian.tools.shell import ShellTool
from guardian.tools.tool_call import (
    TOOL_USE_SYSTEM_ADDITION,
    ToolCall,
    build_tool_result_message,
    parse_tool_calls,
)


@pytest.fixture(autouse=True)
def reset():
    reset_tool_executor()
    yield
    reset_tool_executor()


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def executor(sandbox: Path) -> ToolExecutor:
    exe = ToolExecutor(sandbox_root=sandbox)
    exe.register(FileReadTool())
    exe.register(ShellTool())
    return exe


# ─── ToolCall dataclass ───────────────────────────────────────────────────────

class TestToolCall:
    def test_summary(self):
        call = ToolCall(name="file_read", params={"path": "foo.txt"})
        s = call.summary()
        assert "file_read" in s
        assert "foo.txt" in s


# ─── parse_tool_calls ─────────────────────────────────────────────────────────

class TestParseToolCalls:
    def _block(self, obj: dict) -> str:
        return f"```tool_call\n{json.dumps(obj)}\n```"

    def test_parses_valid_block(self):
        text = self._block({"name": "file_read", "params": {"path": "test.txt"}})
        result = parse_tool_calls(text)
        assert result.has_calls
        assert len(result.calls) == 1
        assert result.calls[0].name == "file_read"
        assert result.calls[0].params == {"path": "test.txt"}

    def test_no_blocks_gives_empty_calls(self):
        result = parse_tool_calls("Just a normal model response.")
        assert not result.has_calls
        assert result.errors == []
        assert result.clean_text == "Just a normal model response."

    def test_multiple_blocks_all_parsed(self):
        text = (
            self._block({"name": "file_read", "params": {"path": "a.txt"}})
            + "\n"
            + self._block({"name": "directory", "params": {"path": "."}})
        )
        result = parse_tool_calls(text)
        assert len(result.calls) == 2
        assert result.calls[0].name == "file_read"
        assert result.calls[1].name == "directory"

    def test_malformed_json_goes_to_errors(self):
        text = "```tool_call\n{not valid json}\n```"
        result = parse_tool_calls(text)
        assert not result.has_calls
        assert result.has_errors
        assert len(result.errors) == 1

    def test_missing_name_goes_to_errors(self):
        text = self._block({"params": {"path": "foo.txt"}})
        result = parse_tool_calls(text)
        assert not result.has_calls
        assert result.has_errors

    def test_params_not_dict_goes_to_errors(self):
        text = self._block({"name": "file_read", "params": "not-a-dict"})
        result = parse_tool_calls(text)
        assert not result.has_calls
        assert result.has_errors

    def test_clean_text_has_blocks_removed(self):
        text = "Before.\n" + self._block({"name": "file_read", "params": {}}) + "\nAfter."
        result = parse_tool_calls(text)
        assert "tool_call" not in result.clean_text
        assert "Before." in result.clean_text
        assert "After." in result.clean_text

    def test_empty_string_gives_no_calls(self):
        result = parse_tool_calls("")
        assert not result.has_calls
        assert result.clean_text == ""

    def test_block_with_empty_params_is_valid(self):
        text = self._block({"name": "directory", "params": {}})
        result = parse_tool_calls(text)
        assert result.has_calls
        assert result.calls[0].params == {}

    def test_raw_field_stored(self):
        obj = {"name": "file_read", "params": {"path": "x.txt"}}
        text = self._block(obj)
        result = parse_tool_calls(text)
        assert result.calls[0].raw != ""


# ─── build_tool_result_message ───────────────────────────────────────────────

class TestBuildToolResultMessage:
    def test_contains_tool_name(self):
        call = ToolCall(name="file_read", params={})
        msg = build_tool_result_message(call, "file contents here")
        assert "file_read" in msg

    def test_contains_result_text(self):
        call = ToolCall(name="file_read", params={})
        msg = build_tool_result_message(call, "file contents here")
        assert "file contents here" in msg

    def test_has_end_marker(self):
        call = ToolCall(name="file_read", params={})
        msg = build_tool_result_message(call, "output")
        assert "[End tool result]" in msg


# ─── TOOL_USE_SYSTEM_ADDITION ────────────────────────────────────────────────

class TestToolUseSystemAddition:
    def test_is_string(self):
        assert isinstance(TOOL_USE_SYSTEM_ADDITION, str)
        assert len(TOOL_USE_SYSTEM_ADDITION) > 100

    def test_mentions_tool_call_format(self):
        assert "tool_call" in TOOL_USE_SYSTEM_ADDITION

    def test_lists_available_tools(self):
        assert "file_read" in TOOL_USE_SYSTEM_ADDITION
        assert "directory" in TOOL_USE_SYSTEM_ADDITION
        assert "search" in TOOL_USE_SYSTEM_ADDITION


# ─── Session.add_raw_assistant_message ───────────────────────────────────────

class TestSessionRawMessages:
    def test_add_raw_message_appears_in_to_messages(self):
        session = Session()
        session.add_raw_assistant_message("Tool result: hello")
        msgs = session.to_messages()
        assert any("Tool result: hello" in m.content for m in msgs)

    def test_raw_role_is_assistant(self):
        session = Session()
        session.add_raw_assistant_message("output")
        msgs = session.to_messages()
        raw = [m for m in msgs if "output" in m.content]
        assert raw[0].role == Role.ASSISTANT

    def test_clear_removes_raw_messages(self):
        session = Session()
        session.add_raw_assistant_message("temp")
        session.clear()
        assert session.to_messages() == []

    def test_raw_messages_come_after_turns(self):
        session = Session()
        session.add_turn("user says", "assistant replies")
        session.add_raw_assistant_message("tool result")
        msgs = session.to_messages()
        # Last message should be the raw one
        assert "tool result" in msgs[-1].content

    def test_multiple_raw_messages(self):
        session = Session()
        session.add_raw_assistant_message("msg1")
        session.add_raw_assistant_message("msg2")
        msgs = session.to_messages()
        assert len(msgs) == 2


# ─── ToolLoop ─────────────────────────────────────────────────────────────────

def make_mock_backend(response: str) -> MockBackend:
    """MockBackend that always returns a fixed response string."""
    mock = MockBackend()
    mock._fixed_response = response
    return mock


class FixedMockBackend(MockBackend):
    """MockBackend that returns a predetermined sequence of responses."""
    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self._responses = list(responses)
        self._index = 0

    def complete(self, request):
        from guardian.model.interface import ModelResponse, TokenUsage
        content = self._responses[self._index % len(self._responses)]
        self._index += 1
        self._call_count += 1  # private attr from MockBackend
        return ModelResponse(
            content=content,
            provider=self.get_info().provider,
            model=self.get_info().model,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class TestToolLoop:
    def _make_tool_call_text(self, name: str, params: dict) -> str:
        return f"```tool_call\n{json.dumps({'name': name, 'params': params})}\n```"

    def test_no_tool_calls_returns_direct_response(self, executor):
        mock = FixedMockBackend(["Hello, no tools needed."])
        core = GuardianCore(model=mock)
        session = Session()
        loop = ToolLoop(executor=executor)

        result = loop.run(core, "hello", session)
        assert result.success
        assert result.total_rounds == 0
        assert "Hello, no tools needed." in result.final_response.content

    def test_level0_tool_auto_approved(self, executor, sandbox):
        # Create a real file in sandbox
        (sandbox / "hello.txt").write_text("file contents", encoding="utf-8")
        tool_call_text = self._make_tool_call_text("file_read", {"path": "hello.txt"})

        mock = FixedMockBackend([
            tool_call_text,              # Round 1: model requests tool
            "I read the file: hello.txt contains 'file contents'.",  # Round 2: final answer
        ])
        core = GuardianCore(model=mock)
        session = Session()

        # Level 0 auto-approve: callback not needed
        loop = ToolLoop(executor=executor, approval_callback=lambda c: True)
        result = loop.run(core, "read hello.txt", session)

        assert result.success
        assert result.total_rounds == 1
        assert result.rounds[0].approved is True
        assert result.rounds[0].success is True

    def test_level2_tool_denied_when_callback_returns_false(self, executor):
        tool_call_text = self._make_tool_call_text("shell", {"command": "echo hi"})
        mock = FixedMockBackend([
            tool_call_text,
            "I could not run the command.",
        ])
        core = GuardianCore(model=mock)
        session = Session()

        # Deny all
        loop = ToolLoop(executor=executor, approval_callback=lambda c: False)
        result = loop.run(core, "run echo hi", session)

        assert result.total_rounds == 1
        assert result.rounds[0].approved is False
        assert "denied" in result.rounds[0].result_text.lower()

    def test_unknown_tool_handled_gracefully(self, executor):
        tool_call_text = self._make_tool_call_text("nonexistent_tool", {"x": "y"})
        mock = FixedMockBackend([
            tool_call_text,
            "I could not use that tool.",
        ])
        core = GuardianCore(model=mock)
        session = Session()
        loop = ToolLoop(executor=executor)

        result = loop.run(core, "use nonexistent", session)
        assert result.total_rounds == 1
        assert not result.rounds[0].approved

    def test_max_rounds_limit_respected(self, executor):
        # Model keeps requesting a tool every response
        tool_call_text = self._make_tool_call_text("directory", {"path": "."})
        responses = [tool_call_text] * (MAX_TOOL_ROUNDS + 5) + ["done"]
        mock = FixedMockBackend(responses)
        core = GuardianCore(model=mock)
        session = Session()
        loop = ToolLoop(executor=executor, approval_callback=lambda c: True)

        result = loop.run(core, "keep listing", session)
        assert result.total_rounds <= MAX_TOOL_ROUNDS

    def test_result_has_rounds_log(self, executor, sandbox):
        (sandbox / "f.txt").write_text("data", encoding="utf-8")
        tool_call_text = self._make_tool_call_text("file_read", {"path": "f.txt"})
        mock = FixedMockBackend([tool_call_text, "Got it."])
        core = GuardianCore(model=mock)
        session = Session()
        loop = ToolLoop(executor=executor, approval_callback=lambda c: True)

        result = loop.run(core, "read f.txt", session)
        assert len(result.rounds) == 1
        assert result.rounds[0].round_number == 1
        assert result.rounds[0].call.name == "file_read"

    def test_summary_string(self, executor):
        mock = FixedMockBackend(["No tools."])
        core = GuardianCore(model=mock)
        session = Session()
        loop = ToolLoop(executor=executor)
        result = loop.run(core, "hi", session)
        s = result.summary()
        assert "rounds=" in s
        assert "success=" in s
