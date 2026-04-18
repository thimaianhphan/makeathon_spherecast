"""
Web Search — Agnes AI Supply Chain Manager.

Pluggable search provider returning SearchHit objects.
Default: DuckDuckGo (no API key required).
Secondary: Tavily (set TAVILY_API_KEY).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.config import WEB_SEARCH_PROVIDER, TAVILY_API_KEY, ENABLE_WEB_SEARCH


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


async def search(query: str, max_results: int = 5) -> list[SearchHit]:
    """Search the web for query. Returns up to max_results hits."""
    if not ENABLE_WEB_SEARCH:
        return []
    if WEB_SEARCH_PROVIDER == "tavily" and TAVILY_API_KEY:
        return await _tavily_search(query, max_results)
    return await _duckduckgo_search(query, max_results)


async def _duckduckgo_search(query: str, max_results: int) -> list[SearchHit]:
    try:
        # Support both legacy `duckduckgo_search` package and new `ddgs` rename
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        import asyncio

        def _sync_search() -> list[SearchHit]:
            results: list[SearchHit] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(SearchHit(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                    ))
            return results

        return await asyncio.get_event_loop().run_in_executor(None, _sync_search)
    except Exception:
        return []


async def _tavily_search(query: str, max_results: int) -> list[SearchHit]:
    try:
        import httpx
        from backend.config import HTTP_TIMEOUT_SECONDS
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_API_KEY, "query": query, "max_results": max_results},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    SearchHit(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("content", "")[:500],
                    )
                    for r in data.get("results", [])
                ]
    except Exception:
        pass
    return []
