"""
Guardian Tool System — Base Types
====================================
Defines the core abstractions for all Guardian tools.

Constitution reference: Section 12 (Tools), Section 3 (Authority Model)

Authority Levels:
  Level 0 — Observe only. Read files, list directories, search.
             No approval required.
  Level 1 — Modify. Write files, create directories.
             Requires explicit approval (approved=True in ToolRequest).
  Level 2 — Potentially destructive. Run shell commands, delete files.
             Requires user confirmation in the CLI every time.

Rules:
  - Every tool invocation is logged (tool name, params summary, result)
  - Tools are sandboxed: paths must resolve within the workspace root
  - Tools never make network calls (that is the model's job)
  - Tool output is always returned to the caller — never silently discarded
  - Large outputs are truncated with a clear marker
  - Errors are captured in ToolResult.error — tools never raise to caller

Permissions: Tools operate within the workspace only.
             No absolute paths outside the workspace unless explicitly allowed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ToolLevel(IntEnum):
    """Authority level required to execute a tool."""
    READ      = 0   # Safe: observe only
    WRITE     = 1   # Requires approval: modifies the workspace
    DANGEROUS = 2   # Requires explicit user confirmation: may be irreversible


@dataclass
class ToolRequest:
    """
    A request to run a specific tool.

    Fields:
        name       The tool identifier (e.g., "file_read")
        params     Tool-specific parameters (e.g., {"path": "guardian/cli.py"})
        approved   Must be True for Level 1+ tools; ignored for Level 0
        context    Why this tool is being called (for logging/transparency)
    """
    name: str
    params: dict[str, Any]
    approved: bool = False
    context: str = ""
    session_id: str = ""


@dataclass
class ToolResult:
    """
    The result of a tool invocation.

    Fields:
        success      True if the tool completed without error
        output       Text output (file contents, command output, listing, etc.)
        error        Error message if success=False; None otherwise
        tool_name    Which tool produced this result
        duration_ms  How long the tool took
        truncated    True if output was cut short due to size limits
        metadata     Additional tool-specific info
    """
    success: bool
    output: str
    error: str | None = None
    tool_name: str = ""
    duration_ms: float = 0.0
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.success

    def summary(self) -> str:
        status = "OK" if self.success else f"ERROR: {self.error}"
        trunc  = " [TRUNCATED]" if self.truncated else ""
        return (
            f"[tool={self.tool_name} "
            f"ms={self.duration_ms:.0f} "
            f"chars={len(self.output)}{trunc} "
            f"status={status}]"
        )


class Tool(ABC):
    """
    Abstract base class for all Guardian tools.

    Subclasses must define:
        name        str identifier used in ToolRequest.name
        level       ToolLevel authority required
        description Short explanation of what this tool does
        _execute()  The actual implementation (never raises)
    """

    name: str
    level: ToolLevel
    description: str

    @abstractmethod
    def _execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool. Must not raise — return error in ToolResult."""

    def schema(self) -> dict[str, Any]:
        """Parameter schema for documentation. Override in subclasses."""
        return {}


class ToolError(Exception):
    """Raised by the executor (not tools themselves) for configuration issues."""


class SandboxViolation(ToolError):
    """Raised when a tool tries to access a path outside the sandbox."""
