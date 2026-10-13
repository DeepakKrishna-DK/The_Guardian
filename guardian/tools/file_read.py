"""
FileReadTool — Level 0 (Read-Only)
=====================================
Reads a file within the Guardian workspace and returns its contents.

Params:
    path     Path to file (relative to sandbox root)
    encoding Optional encoding (default: utf-8)
    max_chars Max characters to return (default: 50_000)
              Outputs beyond this limit are truncated.
    start_line  Optional 1-indexed line to start reading from
    end_line    Optional 1-indexed line to stop reading at (inclusive)

Sandbox:    Enforced — path must resolve inside the workspace.
Authority:  Level 0 — no approval required.
Failure:    Returns ToolResult.success=False with error message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardian.tools.base import SandboxViolation, Tool, ToolLevel, ToolResult

MAX_CHARS = 50_000
TRUNCATION_MARKER = "\n\n[... output truncated — file continues beyond limit ...]"


class FileReadTool(Tool):
    name = "file_read"
    level = ToolLevel.READ
    description = "Read a file within the Guardian workspace (Level 0 — read-only)."

    def schema(self) -> dict[str, Any]:
        return {
            "path": "str (required) — path relative to workspace root",
            "encoding": "str (optional, default: utf-8)",
            "max_chars": f"int (optional, default: {MAX_CHARS})",
            "start_line": "int (optional) — 1-indexed start line",
            "end_line": "int (optional) — 1-indexed end line (inclusive)",
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        raw_path = params.get("path", "")
        if not raw_path:
            return ToolResult(success=False, output="", error="'path' parameter is required")

        sandbox: Path = params["_sandbox"]
        resolve = params["_resolve"]

        try:
            resolved = resolve(raw_path, sandbox)
        except SandboxViolation:
            raise  # Re-raised and caught by executor

        if not resolved.exists():
            return ToolResult(
                success=False, output="",
                error=f"File not found: {raw_path!r}",
            )
        if not resolved.is_file():
            return ToolResult(
                success=False, output="",
                error=f"Path is not a file: {raw_path!r}",
            )

        encoding = params.get("encoding", "utf-8")
        max_chars = int(params.get("max_chars", MAX_CHARS))
        start_line = params.get("start_line")
        end_line = params.get("end_line")

        try:
            text = resolved.read_text(encoding=encoding, errors="replace")
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Read error: {type(exc).__name__}: {exc}",
            )

        # Line range filter
        if start_line is not None or end_line is not None:
            lines = text.splitlines(keepends=True)
            s = (int(start_line) - 1) if start_line else 0
            e = int(end_line) if end_line else len(lines)
            text = "".join(lines[s:e])

        # Truncate
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars] + TRUNCATION_MARKER
            truncated = True

        size_bytes = resolved.stat().st_size
        line_count = text.count("\n") + 1

        return ToolResult(
            success=True,
            output=text,
            truncated=truncated,
            metadata={
                "path": str(resolved),
                "size_bytes": size_bytes,
                "line_count": line_count,
                "encoding": encoding,
            },
        )
