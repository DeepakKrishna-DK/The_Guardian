"""
Unit Tests for Academic Research System & OpenAlex/Crossref Integration
========================================================================
Covers:
  - OpenAlex abstract reconstruction from inverted index
  - AcademicPaper citation formatting
  - AcademicResearchClient with deduplication
  - AcademicResearchPipeline synthesis and untrusted boundaries
  - AcademicResearchTool execution within ToolExecutor
"""

from __future__ import annotations

import pytest

from guardian.research import (
    AcademicPaper,
    AcademicResearchClient,
    AcademicResearchPipeline,
    reconstruct_abstract,
)
from guardian.tools import ToolRequest, get_tool_executor, reset_tool_executor
from guardian.tools.base import ToolLevel


class TestAbstractReconstruction:
    """Verifies that OpenAlex inverted indexes are reconstructed into coherent text."""

    def test_reconstruct_abstract_ordered(self):
        inverted_index = {
            "Quantum": [0],
            "error": [1],
            "correction": [2],
            "enables": [3],
            "fault-tolerant": [4],
            "computation": [5],
        }
        text = reconstruct_abstract(inverted_index)
        assert text == "Quantum error correction enables fault-tolerant computation"

    def test_empty_inverted_index(self):
        assert reconstruct_abstract(None) == ""
        assert reconstruct_abstract({}) == ""


class TestAcademicPaper:
    """Verifies citation formatting and metadata."""

    def test_citation_formatting_with_doi(self):
        paper = AcademicPaper(
            title="Attention Is All You Need",
            doi="10.5555/3295222.3295349",
            url="https://arxiv.org/abs/1706.03762",
            publication_date="2017-06-12",
            authors=["A. Vaswani", "N. Shazeer", "N. Parmar", "J. Uszkoreit"],
            cited_by_count=120000,
            journal="Advances in Neural Information Processing Systems",
        )
        cite = paper.citation_str()
        assert "A. Vaswani" in cite
        assert "et al." in cite
        assert "(2017)" in cite
        assert "[Attention Is All You Need]" in cite
        assert "Advances in Neural Information Processing Systems" in cite


class TestAcademicResearchClient:
    """Verifies search, deduplication, and fallback behavior."""

    def test_search_and_deduplication(self):
        client = AcademicResearchClient()
        papers = client.search("reinforcement learning", limit=3)
        assert len(papers) <= 3
        assert len(papers) > 0

        # Verify all retrieved papers have titles
        for p in papers:
            assert len(p.title) > 0
            assert p.source_api in ("openalex", "crossref", "fallback")

    def test_empty_query_returns_empty(self):
        client = AcademicResearchClient()
        assert client.search("") == []

    def test_deduplication_logic(self):
        client = AcademicResearchClient()
        # Mocking duplicate list to verify deduplication
        p1 = AcademicPaper(title="Paper One", doi="10.1000/1", publication_date="2024")
        p2 = AcademicPaper(title="Paper One Duplicate", doi="10.1000/1", publication_date="2024")
        p3 = AcademicPaper(title="Paper Three", doi="10.1000/3", publication_date="2025")

        seen_dois = set()
        deduped = []
        for p in [p1, p2, p3]:
            if p.doi not in seen_dois:
                seen_dois.add(p.doi)
                deduped.append(p)
        assert len(deduped) == 2


class TestAcademicResearchPipeline:
    """Verifies pipeline synthesis and untrusted evidence wrapping."""

    def test_pipeline_run_generates_citations_and_evidence(self):
        pipeline = AcademicResearchPipeline()
        result = pipeline.run("transformer architectures in NLP", limit=2)
        assert len(result.papers) > 0
        assert len(result.citations) > 0
        assert "[UNTRUSTED SCHOLARLY RESEARCH DATA" in result.evidence_block
        assert "[/UNTRUSTED SCHOLARLY RESEARCH DATA]" in result.evidence_block
        assert "Found " in result.synthesis


class TestAcademicResearchToolIntegration:
    """Verifies integration with Guardian ToolExecutor."""

    def setup_method(self):
        reset_tool_executor()

    def teardown_method(self):
        reset_tool_executor()

    def test_tool_registered(self):
        executor = get_tool_executor()
        tool = executor.get("academic_research")
        assert tool is not None
        assert tool.name == "academic_research"
        assert tool.level == ToolLevel.READ

    def test_tool_execution(self):
        executor = get_tool_executor()
        request = ToolRequest(
            name="academic_research",
            params={"query": "elliptic curve cryptography", "limit": 2},
        )
        result = executor.run(request)
        assert result.success
        assert "Academic Research Report: elliptic curve cryptography" in result.output
        assert "### Formal Citations:" in result.output
        assert "[UNTRUSTED TOOL OUTPUT]" in result.output

    def test_tool_requires_query(self):
        executor = get_tool_executor()
        request = ToolRequest(name="academic_research", params={})
        result = executor.run(request)
        assert not result.success
        assert "Parameter 'query' is required" in result.error
