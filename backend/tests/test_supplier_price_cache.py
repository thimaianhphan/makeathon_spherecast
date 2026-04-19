"""Tests for backend.services.sourcing.price_cache (SQLite-backed evidence cache)."""

from __future__ import annotations

import importlib
import json
from datetime import timedelta
from pathlib import Path

import pytest

from backend.time_utils import utc_now, utc_now_iso
from backend.schemas import SupplierEvidence


def _make_evidence(
    supplier_id: int = 1,
    product_id: int = 10,
    source_type: str = "supplier_site",
    confidence: float = 0.85,
    fetched_at: str | None = None,
) -> SupplierEvidence:
    return SupplierEvidence(
        supplier_id=supplier_id,
        supplier_name="ACME Chemicals",
        candidate_product_id=product_id,
        unit_price_eur=12.50,
        currency_original="USD",
        moq=500,
        lead_time_days=21,
        claimed_certifications=["ISO9001", "HALAL"],
        country_of_origin="DE",
        red_flags=["price_outlier"],
        source_urls=["https://acme.example.com/product/1", "https://acme.example.com/product/2"],
        source_type=source_type,
        confidence=confidence,
        fetched_at=fetched_at or utc_now_iso(),
    )


@pytest.fixture()
def cache_env(tmp_path: Path, monkeypatch):
    """
    Fixture that redirects SQLite to a temp file and re-initialises all modules
    that imported SQLITE_DB_PATH or get_connection at load time.
    """
    db_file = str(tmp_path / "test_cache.sqlite")

    # Patch config first (both the attribute and the env var)
    monkeypatch.setenv("SQLITE_DB_PATH", db_file)
    import backend.config as cfg
    monkeypatch.setattr(cfg, "SQLITE_DB_PATH", db_file)

    # Force db_service to re-resolve its SQLITE_DB_PATH
    import backend.services.db_service as db_service
    monkeypatch.setattr(db_service, "SQLITE_DB_PATH", db_file)

    # (Re)create the table in the temp DB
    from backend.services.db_service import ensure_price_cache_table
    ensure_price_cache_table()

    # Reload price_cache so it picks up the patched db_service
    import backend.services.sourcing.price_cache as pc_module
    importlib.reload(pc_module)

    return pc_module


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_put_then_get_roundtrip(cache_env):
    pc = cache_env
    ev = _make_evidence(supplier_id=1, product_id=10)

    pc.put(ev, product_id=10, material_name="Sunflower Oil")
    result = pc.get(supplier_id=1, product_id=10, ttl_hours=48)

    assert result is not None
    assert result.supplier_id == 1
    assert result.candidate_product_id == 10
    assert result.unit_price_eur == pytest.approx(12.50)
    assert result.currency_original == "USD"
    assert result.moq == 500
    assert result.lead_time_days == 21
    assert result.claimed_certifications == ["ISO9001", "HALAL"]
    assert result.country_of_origin == "DE"
    assert result.red_flags == ["price_outlier"]
    assert result.source_urls == [
        "https://acme.example.com/product/1",
        "https://acme.example.com/product/2",
    ]
    assert result.source_type == "supplier_site"
    assert result.confidence == pytest.approx(0.85)


def test_stale_entry_returns_none(cache_env):
    pc = cache_env
    stale_ts = (utc_now() - timedelta(days=10)).isoformat()
    ev = _make_evidence(supplier_id=2, product_id=20, fetched_at=stale_ts)

    pc.put(ev, product_id=20)
    result = pc.get(supplier_id=2, product_id=20, ttl_hours=168)

    assert result is None


def test_get_many_batch(cache_env):
    pc = cache_env
    now_ts = utc_now_iso()
    stale_ts = (utc_now() - timedelta(days=10)).isoformat()

    # Row 1 — fresh
    pc.put(_make_evidence(supplier_id=1, product_id=100, fetched_at=now_ts), product_id=100)
    # Row 2 — fresh
    pc.put(_make_evidence(supplier_id=2, product_id=200, fetched_at=now_ts), product_id=200)
    # Row 3 — stale
    pc.put(_make_evidence(supplier_id=3, product_id=300, fetched_at=stale_ts), product_id=300)

    result = pc.get_many(
        [(1, 100), (2, 200), (3, 300)],
        ttl_hours=168,
    )

    assert len(result) == 2
    assert (1, 100) in result
    assert (2, 200) in result
    assert (3, 300) not in result
