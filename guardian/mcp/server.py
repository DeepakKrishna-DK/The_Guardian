"""
Guardian MCP Server — Phase 9a
==================================
Exposes Guardian tools over Model Context Protocol (Apache 2.0), mcp 2.x API.
This is a THIN ADAPTER — all logic lives in guardian/tools/ and guardian/knowledge/.

Transport: stdio (run via: guardian mcp serve)
Any MCP-compatible client (Claude Desktop, Open WebUI, Cursor) can call these tools.

L2 shell tool is NOT exposed (requires human-in-the-loop approval).
L0 tools auto-run; L1 file_write requires explicit registration as approved.
"""

from __future__ import annotations

import json

from guardian.logging.logger import get_logger
from guardian.tools import get_tool_executor
from guardian.tools.base import ToolRequest

log = get_logger(__name__)


def _make_mcp_server():
    """Build and return the MCPServer object (mcp >= 2.0)."""
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:
        raise ImportError(
            "mcp >= 2.0 is required. Run: pip install mcp"
        )

    server = MCPServer(
        name="guardian",
        version="0.1.0",
        description=(
            "Guardian AI Platform tools: file_read, directory, search, "
            "knowledge_query, security_audit. Shell (run) is NOT exposed."
        ),
    )

    executor = get_tool_executor()

    @server.tool()
    def file_read(path: str, start_line: int = 0, end_line: int = 0) -> str:
        """
        Read a file within the Guardian workspace.
        start_line and end_line are optional 1-based line numbers (0 = all).
        """
        params: dict = {"path": path}
        if start_line > 0:
            params["start_line"] = start_line
        if end_line > 0:
            params["end_line"] = end_line
        result = executor.run(ToolRequest(name="file_read", params=params, approved=True))
        return result.output if result.success else f"[Error] {result.error}"

    @server.tool()
    def directory(path: str = ".", show_hidden: bool = False) -> str:
        """List contents of a directory within the workspace."""
        result = executor.run(ToolRequest(
            name="directory",
            params={"path": path, "show_hidden": show_hidden},
            approved=True,
        ))
        return result.output if result.success else f"[Error] {result.error}"

    @server.tool()
    def search(
        pattern: str,
        path: str = ".",
        case_sensitive: bool = False,
        context_lines: int = 1,
    ) -> str:
        """Search for a text pattern in files within the workspace."""
        result = executor.run(ToolRequest(
            name="search",
            params={"pattern": pattern, "path": path,
                    "case_sensitive": case_sensitive, "context_lines": context_lines},
            approved=True,
        ))
        return result.output if result.success else f"[Error] {result.error}"

    @server.tool()
    def knowledge_query(question: str, n_results: int = 5) -> str:
        """
        Search Guardian's ingested knowledge base for relevant document chunks.
        Returns the most relevant excerpts with source attribution.
        """
        try:
            from guardian.knowledge import get_knowledge_layer
            kl = get_knowledge_layer()
            if kl.is_empty():
                return "[Knowledge base is empty. Ingest documents first with: guardian knowledge ingest <path>]"
            result = kl.query(question, n_results=n_results)
            if not result.found:
                return f"[No relevant knowledge found for: {question!r}]"
            return result.context
        except Exception as exc:
            log.error(f"MCP knowledge_query error: {exc}")
            return f"[Error] {exc}"

    @server.tool()
    def security_audit() -> str:
        """
        Run Guardian's self-audit scanner (read-only, Level 0).
        Returns a JSON summary of security findings in the workspace.
        """
        try:
            from guardian.security import get_security_guardian, reset_security_guardian
            reset_security_guardian()
            sg = get_security_guardian()
            findings = sg.run_audit(persist=False)
            summary = [
                {"severity": f.severity.value, "category": f.category.value,
                 "title": f.title, "recommendation": f.recommendation}
                for f in findings
            ]
            return json.dumps({"findings": summary, "count": len(summary)}, indent=2)
        except Exception as exc:
            log.error(f"MCP security_audit error: {exc}")
            return f"[Error] {exc}"

    return server


def run_server() -> None:
    """Start the MCP server over stdio (blocking)."""
    log.info("Guardian MCP server starting (stdio transport, mcp 2.x)")
    server = _make_mcp_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    run_server()
