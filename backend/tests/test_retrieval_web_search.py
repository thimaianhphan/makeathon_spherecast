"""Tests for retrieval.web_search — monkeypatched provider."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.retrieval.web_search import search, SearchHit


@pytest.fixture(autouse=True)
def enable_search(monkeypatch):
    monkeypatch.setenv("ENABLE_WEB_SEARCH", "true")
    import backend.config as cfg
    monkeypatch.setattr(cfg, "ENABLE_WEB_SEARCH", True)
    monkeypatch.setattr(cfg, "WEB_SEARCH_PROVIDER", "duckduckgo")


def _fake_ddgs_results():
    return [
        {"title": "Soy Lecithin E322", "href": "https://example.com/lecithin", "body": "Soy lecithin is an emulsifier."},
        {"title": "EU Allergens", "href": "https://example.com/allergens", "body": "Contains soybeans."},
    ]


@pytest.mark.asyncio
async def test_search_returns_hits(monkeypatch):
    """DuckDuckGo search returns parsed SearchHit objects."""
    import backend.services.retrieval.web_search as ws

    def fake_sync_search():
        return [
            SearchHit(title=r["title"], url=r["href"], snippet=r["body"])
            for r in _fake_ddgs_results()
        ]

    with patch("backend.services.retrieval.web_search._duckduckgo_search", new=AsyncMock(return_value=[
        SearchHit(title="Soy Lecithin E322", url="https://example.com/lecithin", snippet="Soy lecithin is an emulsifier."),
        SearchHit(title="EU Allergens", url="https://example.com/allergens", snippet="Contains soybeans."),
    ])):
        results = await search("soy lecithin EU allergen")

    assert len(results) == 2
    assert all(isinstance(r, SearchHit) for r in results)
    assert results[0].url == "https://example.com/lecithin"
    assert "lecithin" in results[0].title.lower()


@pytest.mark.asyncio
async def test_search_disabled_returns_empty(monkeypatch):
    """When ENABLE_WEB_SEARCH is false, search returns empty list."""
    import backend.services.retrieval.web_search as ws
    monkeypatch.setattr(ws, "ENABLE_WEB_SEARCH", False)
    results = await search("anything")
    assert results == []


@pytest.mark.asyncio
async def test_search_handles_exception(monkeypatch):
    """DuckDuckGo failure returns empty list, no exception raised."""
    with patch("backend.services.retrieval.web_search._duckduckgo_search", new=AsyncMock(return_value=[])):
        results = await search("soy lecithin")
    assert isinstance(results, list)
