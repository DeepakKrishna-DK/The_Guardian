"""
WebResearchTool — Level 0 (Read-Only)
=====================================
Enables Guardian agents to search the World Wide Web and extract research evidence.
Enforces SSRF prevention, content sanitization, and citation tracking.
"""

from __future__ import annotations

from typing import Any

from guardian.tools.base import Tool, ToolLevel, ToolResult
from guardian.web.researcher import WebAccessMode, WebResearchOrchestrator


class WebResearchTool(Tool):
    """
    Searches the live web and extracts research findings under strict SSRF & safety controls.
    """
    name = "web_research"
    level = ToolLevel.READ  # Read-only external observation
    description = (
        "Search the live web and retrieve research citations and verified page evidence "
        "(Level 0 — read-only). Enforces SSRF and injection defenses."
    )
    cache_ttl = 180.0  # 3-minute result caching

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search or research query to look up on the web",
                },
                "mode": {
                    "type": "string",
                    "enum": ["research", "continuous_knowledge", "autonomous_agent"],
                    "description": "Web access mode: 'research', 'continuous_knowledge', or 'autonomous_agent'",
                    "default": "research",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of candidate search results to inspect (default: 5)",
                    "default": 5,
                },
                "extract_pages": {
                    "type": "boolean",
                    "description": "Whether to fetch and parse readable text from candidate web pages",
                    "default": True,
                },
                "ingest_to_knowledge": {
                    "type": "boolean",
                    "description": "Whether to index vetted research directly into Guardian's vector knowledge base",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, output="", error="Parameter 'query' is required.")

        raw_mode = str(params.get("mode", "research")).lower()
        try:
            mode = WebAccessMode(raw_mode)
        except ValueError:
            mode = WebAccessMode.RESEARCH

        max_results = int(params.get("max_results", 5))
        extract_pages = bool(params.get("extract_pages", True))
        ingest = bool(params.get("ingest_to_knowledge", False))

        orchestrator = WebResearchOrchestrator()
        report = orchestrator.research(
            query=query,
            mode=mode,
            max_results=max_results,
            extract_pages=extract_pages,
            ingest_to_knowledge=ingest,
        )

        output_parts = [
            f"# Web Research Report: {query}\n",
            f"**Mode**: {mode.value} | **Sources Found**: {report.sources_found} | "
            f"**Pages Read**: {report.pages_extracted} | **Indexed to Knowledge**: {report.ingested_to_knowledge}\n",
            "### Citations:",
        ]

        for cite in report.citations:
            output_parts.append(f"- {cite}")

        output_parts.append("\n" + report.untrusted_context_block)
        full_output = "\n".join(output_parts)

        return ToolResult(
            success=True,
            output=full_output,
            tool_name=self.name,
        )
