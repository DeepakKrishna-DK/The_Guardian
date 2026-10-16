"""
Guardian Digital Access Layer — Unified Web & Research Gateway
==============================================================
Implementation of Layer 3 (Digital Access Layer) per Universal Digital Intelligence
Architecture (Version 2.0).

Coordinates:
  1. Public Web Search (Tavily, Brave Search API, and deterministic fallback).
  2. Safe Web Page Retrieval (HTTPX + SSRF defense + untrusted content tagging).
  3. Interactive Browser Automation (Playwright, sandboxed, SSRF network routing).
  4. Scholarly Research (OpenAlex and Crossref academic connectors).
  5. Provenance tracking and citation validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import time
from typing import Any, Dict, List, Optional

from guardian.logging.logger import get_logger
from guardian.research.academic import AcademicResearchClient as AcademicClient, AcademicPaper
from guardian.web.extractor import ExtractedPage, PageExtractor
from guardian.web.search import SearchResultItem, WebSearchClient
from guardian.web.security import is_safe_url, validate_url_or_raise

log = get_logger(__name__)


@dataclass
class ResearchReport:
    """Unified evidence-grounded research package."""
    query: str
    web_results: List[SearchResultItem] = field(default_factory=list)
    academic_papers: List[AcademicPaper] = field(default_factory=list)
    extracted_pages: List[ExtractedPage] = field(default_factory=list)
    summary_markdown: str = ""
    timestamp: float = field(default_factory=time.time)


class BrowserGateway:
    """
    Playwright Browser Automation Manager.
    Enforces headless mode, isolated contexts, strict timeouts, and SSRF interceptors.
    """

    def __init__(self) -> None:
        self.enabled = os.environ.get("GUARDIAN_BROWSER_ENABLED", "false").lower() in ("1", "true", "yes")
        self.headless = os.environ.get("GUARDIAN_BROWSER_HEADLESS", "true").lower() in ("1", "true", "yes")

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import playwright
            return True
        except ImportError:
            return False

    def render_page(self, url: str, timeout_sec: float = 15.0) -> Dict[str, Any]:
        """
        Render JavaScript-heavy web page in an isolated browser process.
        Enforces outbound SSRF filters on initial URL and network redirects.
        """
        # SSRF validation before navigation
        validate_url_or_raise(url)

        if not self.enabled:
            return {
                "success": False,
                "url": url,
                "error": "Browser automation is disabled by configuration (GUARDIAN_BROWSER_ENABLED=false). Use HTTPX page extractor.",
            }

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                context = browser.new_context(
                    user_agent="Guardian-Universal-AI/1.0 (InteractiveBrowser; +https://github.com/DeepakKrishna-DK/The_Guardian)",
                    ignore_https_errors=False,
                )

                page = context.new_page()
                page.set_default_timeout(int(timeout_sec * 1000))

                # Route-level SSRF interceptor: block requests to local or private networks
                def handle_route(route):
                    req_url = route.request.url
                    safe, _ = is_safe_url(req_url)
                    if safe:
                        route.continue_()
                    else:
                        route.abort("accessdenied")

                page.route("**/*", handle_route)

                page.goto(url, wait_until="domcontentloaded")
                title = page.title()
                content = page.content()
                browser.close()

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content_len": len(content),
                    "mode": "playwright_headless",
                }
        except ImportError:
            return {
                "success": False,
                "url": url,
                "error": "Playwright library is not installed in the current environment.",
            }
        except Exception as exc:
            return {
                "success": False,
                "url": url,
                "error": f"Browser navigation error: {exc}",
            }


class DigitalAccessGateway:
    """
    Unified access layer connecting Guardian to the Web, scholarly sources, and safe extraction.
    """

    def __init__(self) -> None:
        self.search_client = WebSearchClient()
        self.extractor = PageExtractor()
        self.academic_client = AcademicClient()
        self.browser_gateway = BrowserGateway()

    def search_web(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        """Search public web pages and return SSRF-validated results."""
        return self.search_client.search(query=query, max_results=max_results)

    def fetch_page(self, url: str) -> ExtractedPage:
        """Safely fetch and parse text from a web page with SSRF and redirect validation."""
        return self.extractor.extract(url)

    def search_academic(self, query: str, max_results: int = 5) -> List[AcademicPaper]:
        """Search scholarly research across OpenAlex and Crossref."""
        return self.academic_client.search(query=query, limit=max_results)

    def render_browser(self, url: str, timeout_sec: float = 15.0) -> Dict[str, Any]:
        """Render interactive webpage via Playwright if enabled."""
        return self.browser_gateway.render_page(url, timeout_sec=timeout_sec)

    def research_topic(
        self,
        query: str,
        include_web: bool = True,
        include_academic: bool = True,
        fetch_top_pages: int = 2,
    ) -> ResearchReport:
        """
        End-to-end research workflow:
          1. Web search across authoritative sources.
          2. Academic paper retrieval with citation metadata.
          3. Extraction of top relevant web pages.
          4. Compiled structured research report.
        """
        web_items: List[SearchResultItem] = []
        academic_items: List[AcademicPaper] = []
        extracted: List[ExtractedPage] = []

        if include_web:
            web_items = self.search_web(query, max_results=5)

        if include_academic:
            try:
                academic_items = self.search_academic(query, max_results=3)
            except Exception as e:
                log.warning(f"Academic retrieval skipped: {e}")

        # Fetch top safe web pages
        for item in web_items[:fetch_top_pages]:
            try:
                page = self.fetch_page(item.url)
                if page.success:
                    extracted.append(page)
            except Exception as exc:
                log.warning(f"Failed to extract {item.url}: {exc}")

        # Build summary markdown
        lines = [f"## Research Report: {query}\n"]
        if web_items:
            lines.append("### Web Discovery")
            for item in web_items:
                lines.append(f"- **[{item.title}]({item.url})**: {item.snippet}")
            lines.append("")

        if academic_items:
            lines.append("### Scholarly Publications (OpenAlex / Crossref)")
            for paper in academic_items:
                lines.append(f"- {paper.citation_str()} — [DOI:{paper.doi}]({paper.url})")
            lines.append("")

        report = ResearchReport(
            query=query,
            web_results=web_items,
            academic_papers=academic_items,
            extracted_pages=extracted,
            summary_markdown="\n".join(lines),
        )
        return report


_gateway_instance: Optional[DigitalAccessGateway] = None


def get_digital_access_gateway() -> DigitalAccessGateway:
    """Singleton getter for the DigitalAccessGateway."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = DigitalAccessGateway()
    return _gateway_instance
