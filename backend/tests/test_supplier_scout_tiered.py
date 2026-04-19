"""
Comprehensive integration tests for the tier-aware, cache-first supplier scout.

Locks down the behavior so future refactors cannot silently re-introduce
latency (extra HTTP calls) or wasted LLM calls (ai_reason invocations).

Run with:
    pytest backend/tests/test_supplier_scout_tiered.py -v
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from backend.schemas import SupplierEvidence
from backend.time_utils import utc_now_iso


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_evidence(
    supplier_id: int = 7,
    supplier_name: str = "BulkSupplements",
    product_id: int = 999,
    unit_price_eur: float | None = 4.25,
    source_type: str = "supplier_site",
    confidence: float = 0.82,
    claimed_certifications: list[str] | None = None,
) -> SupplierEvidence:
    return SupplierEvidence(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        candidate_product_id=product_id,
        unit_price_eur=unit_price_eur,
        currency_original="USD" if unit_price_eur is not None else None,
        moq=1000 if unit_price_eur is not None else None,
        lead_time_days=7,
        claimed_certifications=claimed_certifications or ["GMP", "NSF"],
        country_of_origin="US",
        red_flags=[],
        source_urls=["https://www.bulksupplements.com/calcium-citrate"],
        source_type=source_type,
        confidence=confidence,
        fetched_at=utc_now_iso(),
    )


# ── Fixture: isolated SQLite + reloaded modules ────────────────────────────────

@pytest.fixture()
def seeded_cache_db(tmp_path: Path, monkeypatch):
    """
    Redirect SQLite to a temp file and re-initialise all modules that imported
    SQLITE_DB_PATH at load time.  Follows the same pattern as
    test_supplier_price_cache.py (cache_env fixture).

    Yields a dict with keys:
        price_cache  – reloaded module
        scout        – reloaded supplier_scout module
        run_cache    – backend.services.sourcing.cache (cleared)
    """
    db_file = str(tmp_path / "tiered_scout.sqlite")

    monkeypatch.setenv("SQLITE_DB_PATH", db_file)

    import backend.config as cfg
    monkeypatch.setattr(cfg, "SQLITE_DB_PATH", db_file)

    import backend.services.db_service as db_service
    monkeypatch.setattr(db_service, "SQLITE_DB_PATH", db_file)

    from backend.services.db_service import ensure_price_cache_table
    ensure_price_cache_table()

    # Reload price_cache so its get_connection picks up the temp DB
    import backend.services.sourcing.price_cache as pc_module
    importlib.reload(pc_module)

    # Reload supplier_scout so it re-imports the reloaded price_cache
    import backend.services.sourcing.subagents.supplier_scout as scout_module
    importlib.reload(scout_module)

    # Reset the in-process run_cache so no stale state leaks across tests
    import backend.services.sourcing.cache as run_cache
    run_cache.clear()

    yield {"price_cache": pc_module, "scout": scout_module, "run_cache": run_cache}


# ── Helper: async runner ──────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test 1: opaque supplier skips network entirely ────────────────────────────

def test_opaque_supplier_skips_network(seeded_cache_db, monkeypatch):
    """
    scout_suppliers for an opaque-tier supplier (ADM) must:
      - never call web_search.search
      - never call web_fetch.fetch_clean
      - return a SupplierEvidence with source_type=='no_evidence', confidence==0.0
    """
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module

    def _should_not_search(*args, **kwargs):
        raise AssertionError("web_search.search should NOT be called for an opaque supplier")

    async def _should_not_fetch(*args, **kwargs):
        raise AssertionError("web_fetch.fetch_clean should NOT be called for an opaque supplier")

    monkeypatch.setattr(ws_module, "search", _should_not_search)
    monkeypatch.setattr(wf_module, "fetch_clean", _should_not_fetch)

    candidates = [{"Id": 100, "SKU": "RM-C1-corn-starch-aabbccdd", "Name": "corn starch"}]
    mappings = [{"supplier_id": 1, "supplier_name": "ADM", "product_id": 100}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    ev = results[0]
    assert ev.source_type == "no_evidence", f"Expected 'no_evidence', got {ev.source_type!r}"
    assert ev.confidence == 0.0, f"Expected confidence 0.0, got {ev.confidence}"
    assert ev.unit_price_eur is None


# ── Test 2: spec_only supplier strips price even when LLM hallucinates ─────────

def test_spec_only_supplier_has_no_price(seeded_cache_db, monkeypatch):
    """
    For a spec_only supplier (Ashland):
      - search returns an ashland.com URL
      - fetch_clean returns a page with cert text but no price
      - ai_reason adversarially returns unit_price_eur=99.99 (hallucinated price)
    Assert:
      - evidence.unit_price_eur is None  (price field coerced to null)
      - source_type == 'supplier_site'
      - claimed_certifications is populated
    """
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module
    import backend.services.agent_service as agent_svc

    from backend.services.retrieval.web_search import SearchHit
    from backend.services.retrieval.web_fetch import FetchedPage

    ashland_url = "https://www.ashland.com/products/calcium-citrate-spec"

    async def _fake_search(query: str, max_results: int = 5):
        return [SearchHit(title="Ashland Calcium Citrate", url=ashland_url, snippet="spec sheet")]

    async def _fake_fetch(url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            title="Ashland Calcium Citrate Spec",
            content="ISO 22000 certified. Halal. Certificate of Analysis available. Contact us for pricing.",
            status_code=200,
        )

    # Adversarial LLM: tries to sneak a price through
    async def _fake_ai_reason(agent_name: str, role: str, prompt: str) -> str:
        return json.dumps({
            "unit_price_eur": 99.99,         # hallucinated — must be stripped
            "currency_original": "EUR",
            "moq": 500,
            "lead_time_days": 14,
            "claimed_certifications": ["ISO 22000", "Halal"],
            "country_of_origin": "US",
            "red_flags": [],
        })

    monkeypatch.setattr(ws_module, "search", _fake_search)
    monkeypatch.setattr(wf_module, "fetch_clean", _fake_fetch)
    monkeypatch.setattr(agent_svc, "ai_reason", _fake_ai_reason)

    candidates = [{"Id": 200, "SKU": "RM-C2-calcium-citrate-05c28cc3", "Name": "calcium citrate"}]
    mappings = [{"supplier_id": 5, "supplier_name": "Ashland", "product_id": 200}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    ev = results[0]
    assert ev.unit_price_eur is None, (
        f"spec_only supplier must NOT expose unit_price_eur; got {ev.unit_price_eur}"
    )
    assert ev.source_type == "supplier_site", f"Expected 'supplier_site', got {ev.source_type!r}"
    assert "ISO 22000" in ev.claimed_certifications or "Halal" in ev.claimed_certifications, (
        f"claimed_certifications should be populated; got {ev.claimed_certifications}"
    )


# ── Test 3: full-tier supplier extracts price ─────────────────────────────────

def test_full_tier_extracts_price(seeded_cache_db, monkeypatch):
    """
    For a full-tier supplier (BulkSupplements):
      - search returns a bulksupplements.com URL
      - fetch_clean returns page content
      - ai_reason returns JSON with price/MOQ/lead_time
    Assert:
      - evidence.unit_price_eur == 12.99
      - source_type == 'supplier_site'
    """
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module
    import backend.services.agent_service as agent_svc

    from backend.services.retrieval.web_search import SearchHit
    from backend.services.retrieval.web_fetch import FetchedPage

    bs_url = "https://www.bulksupplements.com/products/calcium-citrate-powder"

    async def _fake_search(query: str, max_results: int = 5):
        return [SearchHit(title="BulkSupplements Calcium Citrate", url=bs_url, snippet="buy now")]

    async def _fake_fetch(url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            title="Calcium Citrate Powder - BulkSupplements.com",
            content="Calcium Citrate Powder. Price: $14.99 / kg. MOQ: 1 unit. Ships in 3 days. GMP certified.",
            status_code=200,
        )

    async def _fake_ai_reason(agent_name: str, role: str, prompt: str) -> str:
        return json.dumps({
            "unit_price_eur": 12.99,
            "currency_original": "USD",
            "moq": 1,
            "lead_time_days": 3,
            "claimed_certifications": ["GMP"],
            "country_of_origin": "US",
            "red_flags": [],
        })

    monkeypatch.setattr(ws_module, "search", _fake_search)
    monkeypatch.setattr(wf_module, "fetch_clean", _fake_fetch)
    monkeypatch.setattr(agent_svc, "ai_reason", _fake_ai_reason)

    candidates = [{"Id": 300, "SKU": "RM-C3-calcium-citrate-aabbcc11", "Name": "calcium citrate"}]
    mappings = [{"supplier_id": 7, "supplier_name": "BulkSupplements", "product_id": 300}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    ev = results[0]
    assert ev.unit_price_eur == pytest.approx(12.99), (
        f"Expected unit_price_eur=12.99, got {ev.unit_price_eur}"
    )
    assert ev.source_type == "supplier_site", f"Expected 'supplier_site', got {ev.source_type!r}"
    assert ev.moq == 1
    assert ev.lead_time_days == 3


# ── Test 4: query uses cleaned material name and site: scope ──────────────────

def test_query_uses_cleaned_material_name_and_site_scope(seeded_cache_db, monkeypatch):
    """
    The query passed to search() must:
      - contain "calcium citrate" (cleaned from SKU, no prefix/hex-suffix)
      - contain "site:purebulk.com"
      - NOT contain "RM-C1-" or the hex suffix "05c28cc3"
    """
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module
    import backend.services.agent_service as agent_svc

    from backend.services.retrieval.web_fetch import FetchedPage

    captured_queries: list[str] = []

    async def _spy_search(query: str, max_results: int = 5):
        captured_queries.append(query)
        return []  # return empty so we get no_evidence (we only care about the query)

    async def _noop_fetch(url: str) -> FetchedPage:
        return FetchedPage(url=url, title="", content="", status_code=200)

    async def _noop_ai_reason(agent_name: str, role: str, prompt: str) -> str:
        return "{}"

    monkeypatch.setattr(ws_module, "search", _spy_search)
    monkeypatch.setattr(wf_module, "fetch_clean", _noop_fetch)
    monkeypatch.setattr(agent_svc, "ai_reason", _noop_ai_reason)

    sku = "RM-C1-calcium-citrate-05c28cc3"
    candidates = [{"Id": 400, "SKU": sku, "Name": sku}]
    mappings = [{"supplier_id": 9, "supplier_name": "PureBulk", "product_id": 400}]

    _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(captured_queries) >= 1, "search() was never called — test setup error"
    query = captured_queries[0]

    assert "calcium citrate" in query.lower(), (
        f"Query does not contain cleaned material name 'calcium citrate'; got: {query!r}"
    )
    assert "site:purebulk.com" in query.lower(), (
        f"Query does not contain 'site:purebulk.com' for full-tier supplier; got: {query!r}"
    )
    assert "RM-C1-" not in query, f"Query must not contain raw SKU prefix 'RM-C1-'; got: {query!r}"
    assert "05c28cc3" not in query, (
        f"Query must not contain hex suffix '05c28cc3'; got: {query!r}"
    )


# ── Test 5: cache hit short-circuits scrape (persistent cache) ────────────────

def test_cache_hit_short_circuits_scrape(seeded_cache_db, monkeypatch):
    """
    When a fresh entry exists in the persistent Supplier_Price_Cache:
      - scout_suppliers must return it without calling web_search.search
      - returned evidence fields must match the cached entry
    """
    pc = seeded_cache_db["price_cache"]
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module

    # Seed the persistent cache
    seeded = _make_evidence(supplier_id=7, product_id=501, unit_price_eur=4.25)
    pc.put(seeded, product_id=501, material_name="calcium citrate")

    # Any call to web_search.search must fail the test
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("search() must NOT be called when a warm cache hit exists")

    monkeypatch.setattr(ws_module, "search", _should_not_be_called)

    candidates = [{"Id": 501, "SKU": "RM-C1-calcium-citrate-05c28cc3", "Name": "calcium citrate"}]
    mappings = [{"supplier_id": 7, "supplier_name": "BulkSupplements", "product_id": 501}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    ev = results[0]
    assert ev.unit_price_eur == pytest.approx(4.25), (
        f"Expected cached price 4.25, got {ev.unit_price_eur}"
    )
    assert ev.source_type == "supplier_site"
    assert ev.supplier_id == 7
    assert ev.candidate_product_id == 501


# ── Test 6: cache miss writes to persistent cache after scrape ────────────────

def test_cache_miss_writes_to_cache(seeded_cache_db, monkeypatch):
    """
    When the cache is empty, a successful scrape must be persisted so that the
    next call can serve it from cache.  After scout_suppliers returns, calling
    price_cache.get(...) must yield a non-None row with unit_price_eur == 10.0.
    """
    pc = seeded_cache_db["price_cache"]
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module
    import backend.services.agent_service as agent_svc

    from backend.services.retrieval.web_search import SearchHit
    from backend.services.retrieval.web_fetch import FetchedPage

    bs_url = "https://www.bulksupplements.com/products/magnesium-glycinate"

    async def _fake_search(query: str, max_results: int = 5):
        return [SearchHit(title="BulkSupplements Magnesium", url=bs_url, snippet="buy")]

    async def _fake_fetch(url: str) -> FetchedPage:
        return FetchedPage(
            url=url,
            title="Magnesium Glycinate",
            content="Price: $10.99. GMP certified. Same-day shipping.",
            status_code=200,
        )

    async def _fake_ai_reason(agent_name: str, role: str, prompt: str) -> str:
        return json.dumps({
            "unit_price_eur": 10.0,
            "currency_original": "USD",
            "moq": 1,
            "lead_time_days": 2,
            "claimed_certifications": ["GMP"],
            "country_of_origin": "US",
            "red_flags": [],
        })

    monkeypatch.setattr(ws_module, "search", _fake_search)
    monkeypatch.setattr(wf_module, "fetch_clean", _fake_fetch)
    monkeypatch.setattr(agent_svc, "ai_reason", _fake_ai_reason)

    SUPPLIER_ID = 7
    PRODUCT_ID = 601

    candidates = [{"Id": PRODUCT_ID, "SKU": "RM-C5-magnesium-glycinate-deadbeef", "Name": "magnesium glycinate"}]
    mappings = [{"supplier_id": SUPPLIER_ID, "supplier_name": "BulkSupplements", "product_id": PRODUCT_ID}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    assert results[0].unit_price_eur == pytest.approx(10.0)

    # Verify the result was persisted to the cache
    cached = pc.get(supplier_id=SUPPLIER_ID, product_id=PRODUCT_ID, ttl_hours=48)
    assert cached is not None, "Expected a cache entry after a successful scrape, found None"
    assert cached.unit_price_eur == pytest.approx(10.0), (
        f"Cached unit_price_eur mismatch: expected 10.0, got {cached.unit_price_eur}"
    )


# ── Test 7: opaque supplier result is NOT written to cache ────────────────────

def test_opaque_supplier_does_not_pollute_cache(seeded_cache_db, monkeypatch):
    """
    scout_suppliers for an opaque supplier must return no_evidence AND must NOT
    write anything to the persistent Supplier_Price_Cache.
    """
    pc = seeded_cache_db["price_cache"]
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module

    # Guard: search should never be called for opaque suppliers
    def _not_called(*args, **kwargs):
        raise AssertionError("search() must not be called for opaque suppliers")

    monkeypatch.setattr(ws_module, "search", _not_called)

    SUPPLIER_ID = 2
    PRODUCT_ID = 700

    candidates = [{"Id": PRODUCT_ID, "SKU": "RM-C1-corn-syrup-cafebabe", "Name": "corn syrup"}]
    mappings = [{"supplier_id": SUPPLIER_ID, "supplier_name": "ADM", "product_id": PRODUCT_ID}]

    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert results[0].source_type == "no_evidence"

    # Confirm the opaque no_evidence was NOT cached
    cached = pc.get(supplier_id=SUPPLIER_ID, product_id=PRODUCT_ID, ttl_hours=48)
    assert cached is None, (
        f"Opaque no_evidence must NOT be written to the persistent cache; found: {cached}"
    )


# ── Test 8: unknown supplier treated as opaque ────────────────────────────────

def test_unknown_supplier_treated_as_opaque(seeded_cache_db, monkeypatch):
    """
    A supplier name that appears in neither SUPPLIER_ACCESS nor ALIASES
    must be treated as opaque:
      - no call to web_search.search
      - returns no_evidence with confidence == 0.0
      - no exception raised
    """
    scout = seeded_cache_db["scout"]

    import backend.services.retrieval.web_search as ws_module
    import backend.services.retrieval.web_fetch as wf_module

    def _not_called(*args, **kwargs):
        raise AssertionError("search() must not be called for an unknown supplier")

    async def _not_fetched(*args, **kwargs):
        raise AssertionError("fetch_clean() must not be called for an unknown supplier")

    monkeypatch.setattr(ws_module, "search", _not_called)
    monkeypatch.setattr(wf_module, "fetch_clean", _not_fetched)

    SUPPLIER_ID = 99
    PRODUCT_ID = 800

    candidates = [{"Id": PRODUCT_ID, "SKU": "RM-C1-vitamin-c-00ff00ff", "Name": "vitamin c"}]
    mappings = [
        {"supplier_id": SUPPLIER_ID, "supplier_name": "NotARealSupplierXYZ", "product_id": PRODUCT_ID}
    ]

    # Must not raise any exception
    results = _run(scout.scout_suppliers(candidates=candidates, supplier_product_mappings=mappings))

    assert len(results) == 1
    ev = results[0]
    assert ev.source_type == "no_evidence", (
        f"Unknown supplier must yield 'no_evidence'; got {ev.source_type!r}"
    )
    assert ev.confidence == 0.0, f"Expected confidence==0.0 for unknown supplier; got {ev.confidence}"
