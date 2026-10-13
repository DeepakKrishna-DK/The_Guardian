"""
AcademicResearchTool — Level 0 (Read-Only)
==========================================
Enables Guardian to search peer-reviewed scholarly literature (OpenAlex, Crossref).
Returns validated DOIs, authors, publication dates, and abstracts.
"""

from __future__ import annotations

from typing import Any

from guardian.research.pipeline import AcademicResearchPipeline
from guardian.tools.base import Tool, ToolLevel, ToolResult


class AcademicResearchTool(Tool):
    """
    Searches peer-reviewed academic papers across OpenAlex and Crossref.
    """
    name = "academic_research"
    level = ToolLevel.READ  # Read-only external observation
    description = (
        "Search peer-reviewed academic papers and scholarly literature (OpenAlex, Crossref) "
        "with DOIs, citation counts, and structured metadata (Level 0 — read-only)."
    )
    cache_ttl = 300.0  # 5-minute result caching

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Scientific research question, topic, or author to search for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of research publications to retrieve (default: 5)",
                    "default": 5,
                },
                "provider": {
                    "type": "string",
                    "enum": ["all", "openalex", "crossref"],
                    "description": "Scholarly source to query ('all', 'openalex', 'crossref')",
                    "default": "all",
                },
                "ingest_to_knowledge": {
                    "type": "boolean",
                    "description": "Whether to index retrieved papers directly into Guardian's vector knowledge base",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    def _execute(self, params: dict[str, Any]) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, output="", error="Parameter 'query' is required.")

        limit = int(params.get("limit", 5))
        ingest = bool(params.get("ingest_to_knowledge", False))

        pipeline = AcademicResearchPipeline()
        result = pipeline.run(
            question=query,
            limit=limit,
            ingest_to_knowledge=ingest,
        )

        parts = [
            f"# Academic Research Report: {query}\n",
            f"**Publications Retrieved**: {len(result.papers)} | **Indexed to Knowledge**: {result.ingested_count}\n",
            "### Formal Citations:",
        ]

        for cite in result.citations:
            parts.append(f"- {cite}")

        parts.append("\n### Summary of Literature:")
        parts.append(result.synthesis)
        parts.append("\n" + result.evidence_block)

        full_output = "\n".join(parts)

        return ToolResult(
            success=True,
            output=full_output,
            tool_name=self.name,
        )
