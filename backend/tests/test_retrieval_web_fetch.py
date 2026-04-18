"""Tests for retrieval.web_fetch — monkeypatched httpx."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.retrieval.web_fetch import fetch_clean, FetchedPage, _parse_html


FIXTURE_HTML = """<!DOCTYPE html>
<html>
<head><title>Soy Lecithin — Food Grade</title></head>
<body>
  <nav>Menu items here</nav>
  <script>alert('x')</script>
  <main>
    <h1>Soy Lecithin (E322)</h1>
    <p>Soy lecithin is an emulsifier derived from soybeans.
       It is approved under EU Regulation 1333/2008.
       Allergen note: contains soybeans.</p>
  </main>
  <footer>Copyright 2024</footer>
</body>
</html>"""


def test_parse_html_strips_nav_and_scripts():
    """HTML parser removes nav/script/footer and returns clean text."""
    page = _parse_html("https://example.com/lecithin", FIXTURE_HTML, 200)
    assert page.status_code == 200
    assert page.title == "Soy Lecithin — Food Grade"
    assert "Soy Lecithin (E322)" in page.content
    assert "emulsifier" in page.content
    assert "soybeans" in page.content
    # Nav and script content should be stripped
    assert "Menu items" not in page.content
    assert "alert(" not in page.content


def test_parse_html_respects_max_length():
    """Content is capped at MAX_CONTENT_CHARS."""
    from backend.services.retrieval.web_fetch import MAX_CONTENT_CHARS
    long_html = f"<html><body><p>{'x' * 10000}</p></body></html>"
    page = _parse_html("https://example.com/long", long_html, 200)
    assert len(page.content) <= MAX_CONTENT_CHARS


@pytest.mark.asyncio
async def test_fetch_clean_returns_page_for_valid_response(monkeypatch):
    """fetch_clean returns a FetchedPage with content when HTTP 200."""
    from backend.services.retrieval import web_fetch

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
    mock_resp.text = FIXTURE_HTML

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    # Clear cache first
    web_fetch._page_cache.clear()
    web_fetch._robots_cache.clear()

    with patch("backend.services.retrieval.web_fetch._is_allowed", new=AsyncMock(return_value=True)), \
         patch("httpx.AsyncClient", return_value=mock_client):
        page = await fetch_clean("https://example.com/lecithin")

    assert isinstance(page, FetchedPage)
    assert page.status_code == 200
    assert "lecithin" in page.content.lower()
    assert not page.error


@pytest.mark.asyncio
async def test_fetch_clean_returns_error_on_timeout(monkeypatch):
    """Timeout results in FetchedPage with error field set."""
    import httpx
    from backend.services.retrieval import web_fetch

    web_fetch._page_cache.clear()
    web_fetch._robots_cache.clear()

    with patch("backend.services.retrieval.web_fetch._is_allowed", new=AsyncMock(return_value=True)), \
         patch("backend.services.retrieval.web_fetch._fetch", new=AsyncMock(return_value=FetchedPage(
             url="https://example.com/slow", title="", content="", status_code=0, error="timeout"
         ))):
        page = await fetch_clean("https://example.com/slow")

    assert page.error == "timeout"
    assert page.content == ""
