"""
Guardian Web Intelligence & Research Layer — Public API
=======================================================
Usage:
    from guardian.web import (
        WebAccessMode,
        WebResearchOrchestrator,
        WebSearchClient,
        is_safe_url,
    )

    orchestrator = WebResearchOrchestrator()
    report = orchestrator.research("latest NIST post-quantum cryptography standards")
    print(report.citations)
"""

from __future__ import annotations

from guardian.web.extractor import ExtractedPage, PageExtractor
from guardian.web.researcher import (
    ResearchReport,
    WebAccessMode,
    WebResearchOrchestrator,
)
from guardian.web.search import SearchResultItem, WebSearchClient
from guardian.web.security import (
    SSRFViolationError,
    is_safe_url,
    sanitize_web_content,
    validate_url_or_raise,
)

__all__ = [
    "ExtractedPage",
    "PageExtractor",
    "ResearchReport",
    "SSRFViolationError",
    "SearchResultItem",
    "WebAccessMode",
    "WebResearchOrchestrator",
    "WebSearchClient",
    "is_safe_url",
    "sanitize_web_content",
    "validate_url_or_raise",
]
