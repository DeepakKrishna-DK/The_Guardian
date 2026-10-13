"""
FileWriteTool — Level 1 (Write, requires approval)
====================================================
Writes or appends to a file within the Guardian workspace.

Params:
    path     Path to file (relative to sandbox root)
    content  Text content to write
    mode     "write" (default, overwrites) or "append"
    encoding Optional encoding (default: utf-8)

Sandbox:    Enforced — path must resolve inside the workspace.
Authority:  Level 1 — requires ToolRequest.approved=True.
Failure:    Returns ToolResult.success=False with error message.

Safety:
  - Parent directories are created automatically.
  - If mode="write" and file exists, existing content is replaced.
  - Both actions are logged with file path and byte count.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardian.tools.base import SandboxViolation, Tool, ToolLevel, ToolResult


class FileWriteTool(Tool):
    name = "file_write"
    level = ToolLevel.WRITE
    description = "Write or append to a file (Level 1 — requires approval)."

    def schema(self) -> dict[str, Any]:
        return {
            "path": "str (required) — path relative to workspace root",
            "content": "str (required) — text to write",
            "mode": "str (optional) — 'write' (default) or 'append'",
            "encoding": "str (optional, default: utf-8)",
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        raw_path = params.get("path", "")
        content  = params.get("content", "")

        if not raw_path:
            return ToolResult(success=False, output="", error="'path' parameter is required")
        if content == "":
            return ToolResult(success=False, output="", error="'content' parameter is required")

        sandbox: Path = params["_sandbox"]
        resolve = params["_resolve"]

        try:
            resolved = resolve(raw_path, sandbox)
        except SandboxViolation:
            raise

        mode     = params.get("mode", "write")
        encoding = params.get("encoding", "utf-8")

        if mode not in ("write", "append"):
            return ToolResult(
                success=False, output="",
                error=f"Invalid mode {mode!r}. Use 'write' or 'append'.",
            )

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            file_mode = "w" if mode == "write" else "a"
            with open(resolved, file_mode, encoding=encoding) as f:
                f.write(content)
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Write error: {type(exc).__name__}: {exc}",
            )

        bytes_written = len(content.encode(encoding))
        verb = "Wrote" if mode == "write" else "Appended"

        return ToolResult(
            success=True,
            output=f"{verb} {bytes_written} bytes to {resolved}",
            metadata={
                "path": str(resolved),
                "bytes_written": bytes_written,
                "mode": mode,
            },
        )
