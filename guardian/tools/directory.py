"""
DirectoryTool — Level 0 (Read-Only)
======================================
Lists the contents of a directory within the Guardian workspace.

Params:
    path      Path to directory (relative to sandbox root, default: ".")
    max_items Max entries to return (default: 200)
    show_hidden  Include hidden files (default: False)

Sandbox:    Enforced.
Authority:  Level 0 — no approval required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardian.tools.base import SandboxViolation, Tool, ToolLevel, ToolResult

MAX_ITEMS = 200


class DirectoryTool(Tool):
    name = "directory"
    level = ToolLevel.READ
    description = "List directory contents within the workspace (Level 0 — read-only)."

    def schema(self) -> dict[str, Any]:
        return {
            "path": "str (optional, default: workspace root)",
            "max_items": f"int (optional, default: {MAX_ITEMS})",
            "show_hidden": "bool (optional, default: False)",
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        raw_path    = params.get("path", ".")
        max_items   = int(params.get("max_items", MAX_ITEMS))
        show_hidden = bool(params.get("show_hidden", False))

        sandbox: Path = params["_sandbox"]
        resolve = params["_resolve"]

        try:
            resolved = resolve(raw_path, sandbox)
        except SandboxViolation:
            raise

        if not resolved.exists():
            return ToolResult(
                success=False, output="",
                error=f"Directory not found: {raw_path!r}",
            )
        if not resolved.is_dir():
            return ToolResult(
                success=False, output="",
                error=f"Path is not a directory: {raw_path!r}",
            )

        try:
            entries = sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Cannot list directory: {exc}",
            )

        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]

        truncated = len(entries) > max_items
        entries = entries[:max_items]

        lines = [f"Directory: {resolved}\n"]
        for entry in entries:
            if entry.is_dir():
                lines.append(f"  [DIR]  {entry.name}/")
            else:
                size = entry.stat().st_size
                size_str = f"{size:,}" if size < 1_000_000 else f"{size/1e6:.1f}M"
                lines.append(f"  [FILE] {entry.name}  ({size_str} bytes)")

        if truncated:
            lines.append(f"\n  ... (showing {max_items} of {len(entries)}+ entries)")

        return ToolResult(
            success=True,
            output="\n".join(lines),
            truncated=truncated,
            metadata={"path": str(resolved), "count": len(entries)},
        )
