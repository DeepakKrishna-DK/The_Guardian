"""
Guardian Web Extractor — Safe Page Fetcher & Content Extractor
==============================================================
Safely fetches HTML pages, verifies redirect targets against SSRF rules,
strips extraneous DOM elements, and extracts clean, readable text.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import bs4
except ImportError:
    bs4 = None  # type: ignore[assignment]
import httpx

from guardian.logging.logger import get_logger
from guardian.web.security import is_safe_url, sanitize_web_content

log = get_logger(__name__)

MAX_PAGE_BYTES = 2_000_000  # 2MB max download size
REQUEST_TIMEOUT = 12.0


@dataclass
class ExtractedPage:
    """Structured result of fetching and extracting a web page."""
    url: str
    title: str = ""
    text: str = ""
    status_code: int = 0
    success: bool = False
    error: str = ""


class PageExtractor:
    """Fetches and extracts clean textual content from permitted URLs."""

    def __init__(self, timeout_sec: float = REQUEST_TIMEOUT) -> None:
        self.timeout_sec = timeout_sec

    def extract(self, url: str) -> ExtractedPage:
        """
        Safely fetch and parse a web page.
        Validates target URL and redirect destinations against SSRF rules.
        """
        # Step 1: SSRF check
        safe, reason = is_safe_url(url)
        if not safe:
            log.warning(f"Refused unsafe URL: {url} ({reason})")
            return ExtractedPage(url=url, success=False, error=f"SSRF blocked: {reason}")

        # Step 2: Fetch with strict redirect and size checks
        try:
            headers = {
                "User-Agent": "Guardian-Universal-AI/1.0 (ResearchBot; +https://github.com/DeepakKrishna-DK/The_Guardian)",
                "Accept": "text/html,application/xhtml+xml,text/plain",
            }
            with httpx.Client(
                timeout=self.timeout_sec,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                # Custom hook could check redirects; httpx checks initial URL
                resp = client.get(url, headers=headers)

                # Verify final redirected URL
                final_url = str(resp.url)
                final_safe, final_reason = is_safe_url(final_url)
                if not final_safe:
                    return ExtractedPage(
                        url=final_url,
                        status_code=resp.status_code,
                        success=False,
                        error=f"SSRF blocked after redirect: {final_reason}",
                    )

                if len(resp.content) > MAX_PAGE_BYTES:
                    return ExtractedPage(
                        url=final_url,
                        status_code=resp.status_code,
                        success=False,
                        error=f"Page size ({len(resp.content)} bytes) exceeds limit ({MAX_PAGE_BYTES} bytes)",
                    )

                resp.raise_for_status()
                html_text = resp.text

        except httpx.HTTPStatusError as e:
            return ExtractedPage(url=url, status_code=e.response.status_code, success=False, error=str(e))
        except Exception as e:
            return ExtractedPage(url=url, success=False, error=f"Fetch failed: {e}")

        # Step 3: Parse and extract text using BeautifulSoup or fallback
        try:
            if bs4 is not None:
                soup = bs4.BeautifulSoup(html_text, "html.parser")

                # Remove non-content elements
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]):
                    tag.decompose()

                title = (soup.title.string or "").strip() if soup.title else ""
                body_text = soup.get_text(separator="\n")
            else:
                import re
                clean = re.sub(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
                m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.DOTALL | re.IGNORECASE)
                title = m.group(1).strip() if m else ""
                body_text = re.sub(r"<[^>]+>", " ", clean)

            cleaned_text = sanitize_web_content(body_text)

            return ExtractedPage(
                url=final_url,
                title=title,
                text=cleaned_text,
                status_code=resp.status_code,
                success=True,
            )
        except Exception as e:
            return ExtractedPage(url=url, success=False, error=f"Parsing error: {e}")
