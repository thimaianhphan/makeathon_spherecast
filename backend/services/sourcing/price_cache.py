"""
Persistent SQLite cache for supplier price/spec evidence.

Provides get / put / get_many / stats helpers backed by the
Supplier_Price_Cache table (created by db_service.ensure_price_cache_table).
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

import backend.config as _cfg
from backend.schemas import SupplierEvidence
from backend.services.db_service import get_connection
from backend.time_utils import parse_utc_iso, utc_now


def _ttl(ttl_hours: Optional[int]) -> int:
    return ttl_hours if ttl_hours is not None else _cfg.SUPPLIER_PRICE_CACHE_TTL_HOURS


def _row_to_evidence(row) -> SupplierEvidence:
    """Convert a Supplier_Price_Cache sqlite3.Row into a SupplierEvidence."""
    r = dict(row)
    return SupplierEvidence(
        supplier_id=r["supplier_id"],
        supplier_name=r.get("material_name") or "",  # name not stored; fall back gracefully
        candidate_product_id=r["product_id"],
        unit_price_eur=r.get("unit_price_eur"),
        currency_original=r.get("currency_original"),
        moq=r.get("moq"),
        lead_time_days=r.get("lead_time_days"),
        claimed_certifications=json.loads(r["certifications_json"] or "[]"),
        country_of_origin=r.get("country_of_origin"),
        red_flags=json.loads(r["red_flags_json"] or "[]"),
        source_urls=json.loads(r["source_urls_json"] or "[]"),
        source_type=r["source_type"],
        confidence=r["confidence"],
        fetched_at=r["fetched_at"],
    )


def _is_fresh(fetched_at: str, ttl_hours: int) -> bool:
    try:
        age = utc_now() - parse_utc_iso(fetched_at)
        return age <= timedelta(hours=ttl_hours)
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def get(supplier_id: int, product_id: int, ttl_hours: Optional[int] = None) -> Optional[SupplierEvidence]:
    """Return cached evidence if it exists and is within TTL, else None."""
    hours = _ttl(ttl_hours)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM Supplier_Price_Cache WHERE supplier_id = ? AND product_id = ?",
            (supplier_id, product_id),
        ).fetchone()
    if row is None:
        return None
    if not _is_fresh(row["fetched_at"], hours):
        return None
    return _row_to_evidence(row)


def put(evidence: SupplierEvidence, product_id: int, material_name: Optional[str] = None) -> None:
    """Upsert a SupplierEvidence row keyed on (supplier_id, product_id)."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Supplier_Price_Cache (
                supplier_id, product_id, material_name,
                unit_price_eur, currency_original, moq, lead_time_days,
                certifications_json, country_of_origin, red_flags_json,
                source_urls_json, source_type, confidence, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(supplier_id, product_id) DO UPDATE SET
                material_name       = excluded.material_name,
                unit_price_eur      = excluded.unit_price_eur,
                currency_original   = excluded.currency_original,
                moq                 = excluded.moq,
                lead_time_days      = excluded.lead_time_days,
                certifications_json = excluded.certifications_json,
                country_of_origin   = excluded.country_of_origin,
                red_flags_json      = excluded.red_flags_json,
                source_urls_json    = excluded.source_urls_json,
                source_type         = excluded.source_type,
                confidence          = excluded.confidence,
                fetched_at          = excluded.fetched_at
            """,
            (
                evidence.supplier_id,
                product_id,
                material_name,
                evidence.unit_price_eur,
                evidence.currency_original,
                evidence.moq,
                evidence.lead_time_days,
                json.dumps(evidence.claimed_certifications),
                evidence.country_of_origin,
                json.dumps(evidence.red_flags),
                json.dumps(evidence.source_urls),
                evidence.source_type,
                evidence.confidence,
                evidence.fetched_at,
            ),
        )
        conn.commit()


def get_many(
    pairs: list[tuple[int, int]],
    ttl_hours: Optional[int] = None,
) -> dict[tuple[int, int], SupplierEvidence]:
    """
    Batch-read evidence for multiple (supplier_id, product_id) pairs.
    Returns only non-stale rows keyed by (supplier_id, product_id).
    """
    if not pairs:
        return {}
    hours = _ttl(ttl_hours)
    placeholders = ",".join("(?,?)" for _ in pairs)
    flat_params: list[int] = []
    for s, p in pairs:
        flat_params.extend([s, p])

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM Supplier_Price_Cache WHERE (supplier_id, product_id) IN ({placeholders})",
            flat_params,
        ).fetchall()

    result: dict[tuple[int, int], SupplierEvidence] = {}
    for row in rows:
        if _is_fresh(row["fetched_at"], hours):
            key = (row["supplier_id"], row["product_id"])
            result[key] = _row_to_evidence(row)
    return result


def stats() -> dict:
    """Return cache statistics: total, fresh, stale, and breakdown by source_type."""
    hours = _ttl(None)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT supplier_id, product_id, source_type, fetched_at FROM Supplier_Price_Cache"
        ).fetchall()

    total = len(rows)
    fresh = 0
    stale = 0
    by_source: dict[str, int] = {}
    for row in rows:
        src = row["source_type"]
        by_source[src] = by_source.get(src, 0) + 1
        if _is_fresh(row["fetched_at"], hours):
            fresh += 1
        else:
            stale += 1

    return {"total": total, "fresh": fresh, "stale": stale, "by_source_type": by_source}
