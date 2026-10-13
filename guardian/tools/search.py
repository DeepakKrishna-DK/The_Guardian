"""
SearchTool — Level 0 (Read-Only)
==================================
Searches for a text pattern within files in the workspace.

Params:
    pattern    Text to search for (case-insensitive substring by default)
    path       Root path to search in (relative, default: workspace root)
    glob       File glob pattern to match (default: "**/*")
    max_matches  Max results to return (default: 100)
    context_lines  Lines of context around each match (default: 2)
    case_sensitive  Whether the search is case-sensitive (default: False)

Sandbox:    Enforced — only searches within the workspace.
Authority:  Level 0 — no approval required.
Notes:      Binary files are skipped. Very large files may be slower.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardian.tools.base import SandboxViolation, Tool, ToolLevel, ToolResult

MAX_MATCHES    = 100
CONTEXT_LINES  = 2
SKIP_DIRS      = {".git", "__pycache__", "venv", ".venv", "node_modules", ".pytest_cache"}
MAX_FILE_BYTES = 5_000_000  # Skip files > 5MB


class SearchTool(Tool):
    name = "search"
    level = ToolLevel.READ
    description = "Search for text within files in the workspace (Level 0 — read-only)."

    def schema(self) -> dict[str, Any]:
        return {
            "pattern": "str (required) — text to search for",
            "path": "str (optional, default: workspace root)",
            "glob": "str (optional, default: '**/*')",
            "max_matches": f"int (optional, default: {MAX_MATCHES})",
            "context_lines": f"int (optional, default: {CONTEXT_LINES})",
            "case_sensitive": "bool (optional, default: False)",
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(success=False, output="", error="'pattern' parameter is required")

        sandbox: Path = params["_sandbox"]
        resolve = params["_resolve"]

        raw_path = params.get("path", ".")
        try:
            search_root = resolve(raw_path, sandbox)
        except SandboxViolation:
            raise

        if not search_root.exists():
            return ToolResult(
                success=False, output="",
                error=f"Search root not found: {raw_path!r}",
            )

        glob_pattern  = params.get("glob", "**/*")
        max_matches   = int(params.get("max_matches", MAX_MATCHES))
        ctx_lines     = int(params.get("context_lines", CONTEXT_LINES))
        case_sensitive = bool(params.get("case_sensitive", False))

        search_str = pattern if case_sensitive else pattern.lower()

        results: list[str] = []
        match_count = 0
        files_scanned = 0
        truncated = False

        try:
            for file_path in search_root.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                # Skip excluded directories
                if any(skip in file_path.parts for skip in SKIP_DIRS):
                    continue
                # Skip large files
                try:
                    if file_path.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue

                files_scanned += 1

                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                lines = text.splitlines()
                compare_lines = [
                    (l.lower() if not case_sensitive else l) for l in lines
                ]

                for i, cline in enumerate(compare_lines):
                    if search_str in cline:
                        if match_count >= max_matches:
                            truncated = True
                            break

                        # Build context block
                        start = max(0, i - ctx_lines)
                        end   = min(len(lines), i + ctx_lines + 1)
                        rel   = file_path.relative_to(sandbox)

                        block_lines = [f"--- {rel}:{i+1} ---"]
                        for j in range(start, end):
                            marker = ">>>" if j == i else "   "
                            block_lines.append(f"{marker} {j+1:4d}: {lines[j]}")
                        results.append("\n".join(block_lines))
                        match_count += 1

                if truncated:
                    break
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Search error: {type(exc).__name__}: {exc}",
            )

        if not results:
            output = f"No matches for {pattern!r} in {raw_path}"
        else:
            header = f"Found {match_count} match(es) for {pattern!r} across {files_scanned} file(s)"
            if truncated:
                header += f" (showing first {max_matches})"
            output = header + "\n\n" + "\n\n".join(results)

        return ToolResult(
            success=True,
            output=output,
            truncated=truncated,
            metadata={
                "pattern": pattern,
                "match_count": match_count,
                "files_scanned": files_scanned,
            },
        )
