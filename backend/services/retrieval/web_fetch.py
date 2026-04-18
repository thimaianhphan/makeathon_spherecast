"""
Web Fetch — Agnes AI Supply Chain Manager.

Fetches a URL, strips nav/script/style, returns clean main-text content.
Caches by URL. Respects robots.txt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import HTTP_TIMEOUT_SECONDS

_page_cache: dict[str, "FetchedPage"] = {}
_robots_cache: dict[str, bool] = {}

MAX_CONTENT_CHARS = 5000
USER_AGENT = "Agnes-Supply-Chain-Bot/1.0 (research; not-commercial)"


@dataclass
class FetchedPage:
    url: str
    title: str
    content: str  # cleaned main text, capped at MAX_CONTENT_CHARS
    status_code: int
    error: str = ""


async def fetch_clean(url: str) -> FetchedPage:
    """Fetch URL and return cleaned text content."""
    if url in _page_cache:
        return _page_cache[url]

    if not await _is_allowed(url):
        page = FetchedPage(url=url, title="", content="", status_code=0, error="robots.txt disallows")
        _page_cache[url] = page
        return page

    page = await _fetch(url)
    _page_cache[url] = page
    return page


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.TimeoutException),
    reraise=False,
)
async def _fetch(url: str) -> FetchedPage:
    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return FetchedPage(url=url, title="", content="", status_code=resp.status_code,
                                   error=f"HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                return FetchedPage(url=url, title="", content="", status_code=resp.status_code,
                                   error="non-text content")
            return _parse_html(url, resp.text, resp.status_code)
    except httpx.TimeoutException:
        return FetchedPage(url=url, title="", content="", status_code=0, error="timeout")
    except Exception as exc:
        return FetchedPage(url=url, title="", content="", status_code=0, error=str(exc)[:100])


def _parse_html(url: str, html: str, status_code: int) -> FetchedPage:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s{2,}", " ", text)
        return FetchedPage(url=url, title=title, content=text[:MAX_CONTENT_CHARS], status_code=status_code)
    except Exception as exc:
        return FetchedPage(url=url, title="", content="", status_code=status_code, error=str(exc)[:100])


async def _is_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in _robots_cache:
            return _robots_cache[base]
        robots_url = f"{base}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        import asyncio
        await asyncio.get_event_loop().run_in_executor(None, rp.read)
        allowed = rp.can_fetch(USER_AGENT, url)
        _robots_cache[base] = allowed
        return allowed
    except Exception:
        return True  # default allow on error


def clear_cache() -> None:
    _page_cache.clear()
    _robots_cache.clear()
