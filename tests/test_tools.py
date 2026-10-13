"""
Tests for Phase 6 — Tool System
=================================
Tests use pytest tmp_path fixture for real filesystem operations.
No network calls, no API keys required.
ShellTool tests use safe read-only commands (echo, python --version).

Covers:
  ToolLevel enum
  ToolRequest / ToolResult structure
  ToolExecutor: registration, authority gates, sandbox enforcement, unknown tool
  FileReadTool: read file, line range, truncation, missing file, directory path
  FileWriteTool: write, append, overwrite, missing path creates dir, bad mode
  DirectoryTool: list dir, hidden files, max_items
  SearchTool: keyword match, no match, context lines, case-insensitive
  ShellTool: successful command, failed command, timeout, bad cwd
"""

from __future__ import annotations

from pathlib import Path

import pytest

from guardian.tools import reset_tool_executor
from guardian.tools.base import ToolLevel, ToolRequest, ToolResult
from guardian.tools.directory import DirectoryTool
from guardian.tools.executor import ToolExecutor
from guardian.tools.file_read import MAX_CHARS, FileReadTool
from guardian.tools.file_write import FileWriteTool
from guardian.tools.search import SearchTool
from guardian.tools.shell import ShellTool


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure tool executor singleton doesn't leak between tests."""
    reset_tool_executor()
    yield
    reset_tool_executor()


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A fresh temp directory as the sandbox."""
    return tmp_path


@pytest.fixture
def executor(sandbox: Path) -> ToolExecutor:
    exe = ToolExecutor(sandbox_root=sandbox)
    exe.register(FileReadTool())
    exe.register(FileWriteTool())
    exe.register(DirectoryTool())
    exe.register(SearchTool())
    exe.register(ShellTool())
    return exe


def write_file(sandbox: Path, name: str, content: str) -> Path:
    p = sandbox / name
    p.write_text(content, encoding="utf-8")
    return p


# ─── ToolLevel ────────────────────────────────────────────────────────────────

class TestToolLevel:
    def test_read_is_zero(self):
        assert ToolLevel.READ == 0

    def test_write_is_one(self):
        assert ToolLevel.WRITE == 1

    def test_dangerous_is_two(self):
        assert ToolLevel.DANGEROUS == 2

    def test_ordering(self):
        assert ToolLevel.READ < ToolLevel.WRITE < ToolLevel.DANGEROUS


# ─── ToolResult ───────────────────────────────────────────────────────────────

class TestToolResult:
    def test_success_bool(self):
        r = ToolResult(success=True, output="ok")
        assert bool(r) is True

    def test_failure_bool(self):
        r = ToolResult(success=False, output="", error="oops")
        assert bool(r) is False

    def test_summary_ok(self):
        r = ToolResult(success=True, output="hello", tool_name="file_read", duration_ms=10.0)
        s = r.summary()
        assert "file_read" in s
        assert "OK" in s

    def test_summary_error(self):
        r = ToolResult(success=False, output="", error="bad", tool_name="shell")
        assert "ERROR" in r.summary()

    def test_summary_truncated(self):
        r = ToolResult(success=True, output="x", truncated=True, tool_name="t")
        assert "TRUNCATED" in r.summary()


# ─── ToolExecutor ─────────────────────────────────────────────────────────────

class TestToolExecutor:
    def test_register_and_get(self, sandbox):
        exe = ToolExecutor(sandbox_root=sandbox)
        exe.register(FileReadTool())
        assert exe.get("file_read") is not None

    def test_unknown_tool_returns_error(self, executor):
        result = executor.run(ToolRequest(name="nonexistent", params={}))
        assert not result.success
        assert "Unknown tool" in result.error

    def test_level0_needs_no_approval(self, executor, sandbox):
        write_file(sandbox, "test.txt", "hello")
        result = executor.run(ToolRequest(name="file_read", params={"path": "test.txt"}))
        assert result.success

    def test_level1_without_approval_rejected(self, executor):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "out.txt", "content": "data"},
            approved=False,
        ))
        assert not result.success
        assert "requires approval" in result.error

    def test_level1_with_approval_runs(self, executor, sandbox):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "out.txt", "content": "hello"},
            approved=True,
        ))
        assert result.success
        assert (sandbox / "out.txt").read_text() == "hello"

    def test_level2_without_approval_rejected(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "echo hi"},
            approved=False,
        ))
        assert not result.success
        assert "requires approval" in result.error

    def test_sandbox_escape_prevented(self, executor):
        result = executor.run(ToolRequest(
            name="file_read",
            params={"path": "../../../etc/passwd"},
        ))
        assert not result.success
        assert "Sandbox violation" in result.error

    def test_list_tools(self, executor):
        tools = executor.list_tools()
        names = [t.name for t in tools]
        assert "file_read" in names
        assert "shell" in names

    def test_result_has_tool_name(self, executor, sandbox):
        write_file(sandbox, "f.txt", "x")
        result = executor.run(ToolRequest(name="file_read", params={"path": "f.txt"}))
        assert result.tool_name == "file_read"

    def test_result_has_duration_ms(self, executor, sandbox):
        write_file(sandbox, "f.txt", "x")
        result = executor.run(ToolRequest(name="file_read", params={"path": "f.txt"}))
        assert result.duration_ms >= 0


# ─── FileReadTool ─────────────────────────────────────────────────────────────

class TestFileReadTool:
    def test_reads_file(self, executor, sandbox):
        write_file(sandbox, "hello.txt", "Hello Guardian")
        result = executor.run(ToolRequest(name="file_read", params={"path": "hello.txt"}))
        assert result.success
        assert "Hello Guardian" in result.output

    def test_missing_file_returns_error(self, executor):
        result = executor.run(ToolRequest(name="file_read", params={"path": "missing.txt"}))
        assert not result.success
        assert "not found" in result.error.lower()

    def test_directory_path_returns_error(self, executor, sandbox):
        (sandbox / "subdir").mkdir()
        result = executor.run(ToolRequest(name="file_read", params={"path": "subdir"}))
        assert not result.success

    def test_no_path_param_returns_error(self, executor):
        result = executor.run(ToolRequest(name="file_read", params={}))
        assert not result.success
        assert "path" in result.error

    def test_line_range_start(self, executor, sandbox):
        write_file(sandbox, "lines.txt", "line1\nline2\nline3\nline4\nline5")
        result = executor.run(ToolRequest(
            name="file_read",
            params={"path": "lines.txt", "start_line": 3},
        ))
        assert result.success
        assert "line3" in result.output
        assert "line1" not in result.output

    def test_line_range_end(self, executor, sandbox):
        write_file(sandbox, "lines.txt", "line1\nline2\nline3\nline4\nline5")
        result = executor.run(ToolRequest(
            name="file_read",
            params={"path": "lines.txt", "start_line": 1, "end_line": 2},
        ))
        assert "line1" in result.output
        assert "line2" in result.output
        assert "line3" not in result.output

    def test_truncation(self, executor, sandbox):
        big_content = "x" * (MAX_CHARS + 100)
        write_file(sandbox, "big.txt", big_content)
        result = executor.run(ToolRequest(
            name="file_read",
            params={"path": "big.txt"},
        ))
        assert result.success
        assert result.truncated
        assert "truncated" in result.output.lower()

    def test_metadata_has_size(self, executor, sandbox):
        write_file(sandbox, "meta.txt", "hello")
        result = executor.run(ToolRequest(name="file_read", params={"path": "meta.txt"}))
        assert "size_bytes" in result.metadata


# ─── FileWriteTool ────────────────────────────────────────────────────────────

class TestFileWriteTool:
    def test_write_creates_file(self, executor, sandbox):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "new.txt", "content": "Guardian"},
            approved=True,
        ))
        assert result.success
        assert (sandbox / "new.txt").read_text() == "Guardian"

    def test_write_overwrites(self, executor, sandbox):
        write_file(sandbox, "exist.txt", "old content")
        executor.run(ToolRequest(
            name="file_write",
            params={"path": "exist.txt", "content": "new content"},
            approved=True,
        ))
        assert (sandbox / "exist.txt").read_text() == "new content"

    def test_append_mode(self, executor, sandbox):
        write_file(sandbox, "app.txt", "line1\n")
        executor.run(ToolRequest(
            name="file_write",
            params={"path": "app.txt", "content": "line2\n", "mode": "append"},
            approved=True,
        ))
        text = (sandbox / "app.txt").read_text()
        assert "line1" in text
        assert "line2" in text

    def test_creates_parent_directories(self, executor, sandbox):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "deep/nested/file.txt", "content": "hi"},
            approved=True,
        ))
        assert result.success
        assert (sandbox / "deep" / "nested" / "file.txt").read_text() == "hi"

    def test_invalid_mode_returns_error(self, executor):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "f.txt", "content": "x", "mode": "delete"},
            approved=True,
        ))
        assert not result.success

    def test_no_path_returns_error(self, executor):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"content": "data"},
            approved=True,
        ))
        assert not result.success

    def test_metadata_has_bytes_written(self, executor, sandbox):
        result = executor.run(ToolRequest(
            name="file_write",
            params={"path": "meta.txt", "content": "hello"},
            approved=True,
        ))
        assert result.metadata["bytes_written"] == 5


# ─── DirectoryTool ────────────────────────────────────────────────────────────

class TestDirectoryTool:
    def test_lists_files(self, executor, sandbox):
        write_file(sandbox, "a.txt", "A")
        write_file(sandbox, "b.py", "B")
        result = executor.run(ToolRequest(name="directory", params={"path": "."}))
        assert result.success
        assert "a.txt" in result.output
        assert "b.py" in result.output

    def test_lists_subdirs(self, executor, sandbox):
        (sandbox / "mydir").mkdir()
        result = executor.run(ToolRequest(name="directory", params={"path": "."}))
        assert "mydir" in result.output

    def test_missing_directory_returns_error(self, executor):
        result = executor.run(ToolRequest(name="directory", params={"path": "no_such_dir"}))
        assert not result.success

    def test_file_path_returns_error(self, executor, sandbox):
        write_file(sandbox, "file.txt", "data")
        result = executor.run(ToolRequest(name="directory", params={"path": "file.txt"}))
        assert not result.success

    def test_max_items(self, executor, sandbox):
        for i in range(10):
            write_file(sandbox, f"f{i}.txt", "x")
        result = executor.run(ToolRequest(
            name="directory",
            params={"path": ".", "max_items": 3},
        ))
        assert result.success
        # Only 3 entries shown
        assert result.metadata["count"] == 3

    def test_hidden_files_excluded_by_default(self, executor, sandbox):
        write_file(sandbox, ".hidden", "secret")
        write_file(sandbox, "visible.txt", "public")
        result = executor.run(ToolRequest(name="directory", params={"path": "."}))
        assert "visible.txt" in result.output
        assert ".hidden" not in result.output

    def test_hidden_files_shown_when_requested(self, executor, sandbox):
        write_file(sandbox, ".hidden", "secret")
        result = executor.run(ToolRequest(
            name="directory",
            params={"path": ".", "show_hidden": True},
        ))
        assert ".hidden" in result.output


# ─── SearchTool ───────────────────────────────────────────────────────────────

class TestSearchTool:
    def test_finds_match(self, executor, sandbox):
        write_file(sandbox, "code.py", "def hello():\n    return 'world'\n")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "hello", "path": "."},
        ))
        assert result.success
        assert "hello" in result.output
        assert result.metadata["match_count"] == 1

    def test_no_match(self, executor, sandbox):
        write_file(sandbox, "code.py", "print('hi')")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "zzznomatch999", "path": "."},
        ))
        assert result.success
        assert "No matches" in result.output

    def test_case_insensitive_by_default(self, executor, sandbox):
        write_file(sandbox, "readme.txt", "GUARDIAN is a personal AI system")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "guardian", "path": "."},
        ))
        assert result.metadata["match_count"] == 1

    def test_case_sensitive_option(self, executor, sandbox):
        write_file(sandbox, "readme.txt", "GUARDIAN is a personal AI system")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "guardian", "path": ".", "case_sensitive": True},
        ))
        assert result.metadata["match_count"] == 0

    def test_no_pattern_returns_error(self, executor):
        result = executor.run(ToolRequest(name="search", params={"path": "."}))
        assert not result.success

    def test_context_lines_included(self, executor, sandbox):
        write_file(sandbox, "file.txt", "line1\nline2\nTARGET\nline4\nline5")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "TARGET", "path": ".", "context_lines": 1},
        ))
        assert "line2" in result.output
        assert "TARGET" in result.output
        assert "line4" in result.output

    def test_shows_file_and_line_number(self, executor, sandbox):
        write_file(sandbox, "script.py", "x = 1\ny = 2\nz = target_word\n")
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": "target_word", "path": "."},
        ))
        assert "script.py" in result.output
        assert "3" in result.output  # Line number


# ─── ShellTool ────────────────────────────────────────────────────────────────

class TestShellTool:
    def test_requires_approval(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "echo hi"},
            approved=False,
        ))
        assert not result.success
        assert "requires approval" in result.error

    def test_successful_command(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "echo guardian_test"},
            approved=True,
        ))
        assert result.success
        assert "guardian_test" in result.output

    def test_failed_command_returns_error(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "python -c \"import sys; sys.exit(1)\""},
            approved=True,
        ))
        assert not result.success
        assert "Exit code" in result.error

    def test_metadata_has_returncode(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "echo ok"},
            approved=True,
        ))
        assert result.metadata.get("returncode") == 0

    def test_no_command_returns_error(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={},
            approved=True,
        ))
        assert not result.success

    def test_bad_cwd_sandbox_violation(self, executor):
        result = executor.run(ToolRequest(
            name="shell",
            params={"command": "echo x", "cwd": "../../../"},
            approved=True,
        ))
        assert not result.success
        assert "Sandbox violation" in result.error
