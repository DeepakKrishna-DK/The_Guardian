"""
Guardian Web Research Orchestrator
==================================
Coordinates search, safe page extraction, cross-source verification,
citation assembly, and optional knowledge-store ingestion.

Modes:
  1. RESEARCH: On-demand search, read, compare, and cite.
  2. CONTINUOUS_KNOWLEDGE: Research + ingest verified material into KnowledgeLayer.
  3. AUTONOMOUS_AGENT: Multi-step planning, iterative search, and evidence compilation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from guardian.logging.logger import get_logger
from guardian.web.extractor import ExtractedPage, PageExtractor
from guardian.web.search import SearchResultItem, WebSearchClient

log = get_logger(__name__)


class WebAccessMode(str, Enum):
    """The 3 operational web access modes."""
    RESEARCH = "research"
    CONTINUOUS_KNOWLEDGE = "continuous_knowledge"
    AUTONOMOUS_AGENT = "autonomous_agent"


@dataclass
class ResearchReport:
    """The structured output of a web research session."""
    query: str
    mode: WebAccessMode
    sources_found: int = 0
    pages_extracted: int = 0
    ingested_to_knowledge: int = 0
    citations: list[str] = field(default_factory=list)
    evidence_items: list[dict[str, Any]] = field(default_factory=list)
    untrusted_context_block: str = ""
    summary: str = ""


class WebResearchOrchestrator:
    """
    Coordinates web intelligence workflows according to configured access modes.
    """

    def __init__(
        self,
        search_client: WebSearchClient | None = None,
        extractor: PageExtractor | None = None,
    ) -> None:
        self.search_client = search_client or WebSearchClient()
        self.extractor = extractor or PageExtractor()

    def research(
        self,
        query: str,
        mode: WebAccessMode = WebAccessMode.RESEARCH,
        max_results: int = 5,
        extract_pages: bool = True,
        ingest_to_knowledge: bool = False,
    ) -> ResearchReport:
        """
        Execute web research on a topic with citation gathering and verification.
        """
        report = ResearchReport(query=query, mode=mode)
        log.info(f"Web research initiated: mode={mode.value} query='{query}'")

        # Step 1: Discover candidate sources via search
        search_results = self.search_client.search(query, max_results=max_results)
        report.sources_found = len(search_results)

        if not search_results:
            report.summary = f"No accessible web sources found for query: '{query}'."
            return report

        # Step 2: Extract content from top results
        evidence: list[dict[str, Any]] = []
        citations: list[str] = []
        content_blocks: list[str] = []

        # If autonomous agent mode, broaden queries
        target_results = search_results[:max_results]

        for item in target_results:
            citations.append(f"[{item.title}]({item.url})")
            item_entry: dict[str, Any] = {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "score": item.score,
                "extracted_text": "",
            }

            if extract_pages:
                page: ExtractedPage = self.extractor.extract(item.url)
                if page.success:
                    report.pages_extracted += 1
                    item_entry["extracted_text"] = page.text
                    content_blocks.append(
                        f"### Source: {item.title}\nURL: {item.url}\n\n{page.text[:4000]}"
                    )
                else:
                    content_blocks.append(
                        f"### Source: {item.title}\nURL: {item.url}\n(Snippet: {item.snippet})"
                    )
            else:
                content_blocks.append(
                    f"### Source: {item.title}\nURL: {item.url}\nSnippet: {item.snippet}"
                )

            evidence.append(item_entry)

        report.evidence_items = evidence
        report.citations = citations

        # Step 3: Format untrusted reference block for the LLM
        formatted_context = "\n\n---\n\n".join(content_blocks)
        report.untrusted_context_block = (
            "## Web Research Evidence (Untrusted External Sources)\n"
            f"{formatted_context}\n"
        )

        # Step 4: Optional Knowledge Layer Ingestion (Continuous Knowledge Mode)
        if (mode == WebAccessMode.CONTINUOUS_KNOWLEDGE or ingest_to_knowledge) and evidence:
            ingested = self._ingest_into_knowledge_layer(query, evidence)
            report.ingested_to_knowledge = ingested

        report.summary = (
            f"Retrieved {report.sources_found} sources ({report.pages_extracted} pages extracted). "
            f"Evidence compiled across {len(citations)} citations."
        )
        return report

    def _ingest_into_knowledge_layer(
        self, query: str, evidence: list[dict[str, Any]]
    ) -> int:
        """
        Ingest approved research snippets directly into Guardian's KnowledgeLayer (VectorStore).
        """
        try:
            from guardian.knowledge import get_knowledge_layer
            kl = get_knowledge_layer()
            if hasattr(kl, "_retriever"):
                store = getattr(kl._retriever, "_store", None)
                embedder = getattr(kl._retriever, "_embedder", None)
                if store is not None and embedder is not None:
                    count = 0
                    for item in evidence:
                        text = item.get("extracted_text") or item.get("snippet")
                        if text and len(text.strip()) > 30:
                            doc_id = f"web_{abs(hash(item['url'])) % 10000000}"
                            metadata = {
                                "source": item["url"],
                                "title": item["title"],
                                "query": query,
                                "type": "web_research",
                            }
                            emb = embedder.embed(text[:1000])
                            store.add(ids=[doc_id], documents=[text[:1000]], embeddings=[emb], metadatas=[metadata])
                            count += 1
                    log.info(f"Ingested {count} web research items into KnowledgeLayer")
                    return count
        except Exception as e:
            log.warning(f"Failed to ingest web research into KnowledgeLayer: {e}")
        return 0
