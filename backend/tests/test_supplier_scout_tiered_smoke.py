"""
Smoke test: tiered supplier scout with persistent price cache.

Verifies that a warm cache hit:
  - skips all HTTP/search calls entirely, and
  - returns evidence indistinguishable from freshly-scraped rows.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from backend.schemas import SupplierEvidence
from backend.time_utils import utc_now_iso


# ── Fixture: isolated SQLite + reloaded modules ───────────────────────────────

@pytest.fixture()
def cache_env(tmp_path: Path, monkeypatch):
    """
    Redirect SQLite to a temp file, re-initialise all modules that captured
    SQLITE_DB_PATH at import time, and create the Supplier_Price_Cache table.
    Follows the same pattern as test_supplier_price_cache.py.
    """
    db_file = str(tmp_path / "scout_smoke.sqlite")

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

    # Reset the in-process run_cache so no stale state leaks in
    import backend.services.sourcing.cache as run_cache
    run_cache.clear()

    return {"price_cache": pc_module, "scout": scout_module, "run_cache": run_cache}


# ── Helper: build a SupplierEvidence fixture ──────────────────────────────────

def _make_evidence(
    supplier_id: int = 7,
    product_id: int = 999,
    unit_price_eur: float = 4.25,
) -> SupplierEvidence:
    return SupplierEvidence(
        supplier_id=supplier_id,
        supplier_name="BulkSupplements",
        candidate_product_id=product_id,
        unit_price_eur=unit_price_eur,
        currency_original="USD",
        moq=1000,
        lead_time_days=7,
        claimed_certifications=["GMP", "NSF"],
        country_of_origin="US",
        red_flags=[],
        source_urls=["https://www.bulksupplements.com/calcium-citrate"],
        source_type="supplier_site",
        confidence=0.82,
        fetched_at=utc_now_iso(),
    )


# ── Test ──────────────────────────────────────────────────────────────────────

def test_cache_hit_skips_network(cache_env, monkeypatch):
    """
    Seeding the persistent cache for (supplier_id=7, product_id=999) must cause
    scout_suppliers() to return that evidence directly, without ever calling
    web_search.search.
    """
    import asyncio

    pc = cache_env["price_cache"]
    scout = cache_env["scout"]

    # Seed the persistent cache
    seeded = _make_evidence(supplier_id=7, product_id=999, unit_price_eur=4.25)
    pc.put(seeded, product_id=999, material_name="calcium citrate")

    # Any call to web_search.search must fail the test
    import backend.services.retrieval.web_search as ws_module
    monkeypatch.setattr(
        ws_module,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("web_search.search should not be called for a cache hit")
        ),
    )

    candidates = [
        {
            "Id": 999,
            "SKU": "RM-C1-calcium-citrate-05c28cc3",
            "Name": "RM-C1-calcium-citrate-05c28cc3",
        }
    ]
    supplier_product_mappings = [
        {
            "supplier_id": 7,
            "supplier_name": "BulkSupplements",
            "product_id": 999,
        }
    ]

    results: list[SupplierEvidence] = asyncio.run(
        scout.scout_suppliers(
            candidates=candidates,
            supplier_product_mappings=supplier_product_mappings,
        )
    )

    assert len(results) == 1, f"Expected 1 evidence record, got {len(results)}"
    ev = results[0]

    assert ev.unit_price_eur == pytest.approx(4.25), (
        f"unit_price_eur mismatch: expected 4.25, got {ev.unit_price_eur}"
    )
    assert ev.source_type == "supplier_site", (
        f"source_type mismatch: expected 'supplier_site', got {ev.source_type!r}"
    )
    assert ev.supplier_id == 7
    assert ev.candidate_product_id == 999
