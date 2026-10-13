"""
ShellTool — Level 2 (Dangerous, requires confirmation)
=======================================================
Runs a shell command within the Guardian workspace.

Params:
    command   The command to run (string)
    cwd       Working directory (relative to sandbox, default: workspace root)
    timeout   Timeout in seconds (default: 30, max: 120)
    encoding  Output encoding (default: utf-8)

Sandbox:    cwd is enforced within the workspace.
            The command itself is NOT sandboxed (user is responsible).
Authority:  Level 2 — requires ToolRequest.approved=True AND explicit
            user confirmation in the CLI layer.

WARNING: This tool can execute arbitrary shell commands.
         Guardian presents the exact command before running it.
         The user must type an explicit confirmation to proceed.

Output:     stdout + stderr (combined), up to 10,000 chars.
            Truncated output has a marker appended.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from guardian.tools.base import SandboxViolation, Tool, ToolLevel, ToolResult

MAX_OUTPUT_CHARS = 10_000
DEFAULT_TIMEOUT  = 30
MAX_TIMEOUT      = 120
TRUNCATION_MARKER = "\n\n[... output truncated ...]"


class ShellTool(Tool):
    name = "shell"
    level = ToolLevel.DANGEROUS
    description = "Run a shell command (Level 2 — requires explicit user confirmation)."

    def schema(self) -> dict[str, Any]:
        return {
            "command": "str (required) — shell command to execute",
            "cwd": "str (optional, default: workspace root)",
            "timeout": f"int (optional, default: {DEFAULT_TIMEOUT}, max: {MAX_TIMEOUT})",
            "encoding": "str (optional, default: utf-8)",
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        command = params.get("command", "").strip()
        if not command:
            return ToolResult(success=False, output="", error="'command' parameter is required")

        sandbox: Path = params["_sandbox"]
        resolve = params["_resolve"]

        raw_cwd = params.get("cwd", ".")
        try:
            cwd = resolve(raw_cwd, sandbox)
        except SandboxViolation:
            raise

        timeout  = min(int(params.get("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)
        encoding = params.get("encoding", "utf-8")

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding=encoding,
                errors="replace",
                cwd=str(cwd),
                timeout=timeout,
            )
            combined = proc.stdout
            if proc.stderr:
                combined = combined + ("\n" if combined else "") + "[stderr]\n" + proc.stderr
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output="",
                error=f"Command timed out after {timeout}s: {command!r}",
            )
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Execution error: {type(exc).__name__}: {exc}",
            )

        truncated = False
        if len(combined) > MAX_OUTPUT_CHARS:
            combined = combined[:MAX_OUTPUT_CHARS] + TRUNCATION_MARKER
            truncated = True

        return ToolResult(
            success=(proc.returncode == 0),
            output=combined or "(no output)",
            error=None if proc.returncode == 0 else f"Exit code {proc.returncode}",
            truncated=truncated,
            metadata={
                "command": command,
                "returncode": proc.returncode,
                "cwd": str(cwd),
            },
        )
