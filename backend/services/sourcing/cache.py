"""
In-memory cache for sourcing pipeline — reset at the start of each orchestrator run.

Separate from the file-backed evidence_store; this cache lives only for the
duration of one SourcingOrchestrator.run() call to prevent redundant web fetches
and LLM classification calls across parallel raw-material pipelines.
"""

from __future__ import annotations

from backend.schemas import SupplierEvidence

# (supplier_id, candidate_product_id) → SupplierEvidence
_scout_cache: dict[tuple[int, int], SupplierEvidence] = {}

# product_id → classification dict {category, allergens, food_categories, e_number}
_classification_cache: dict[int, dict] = {}

# supplier_id → product count (proxy for supplier scale)
_supplier_scale: dict[int, int] = {}
_supplier_scales_loaded: bool = False


def clear() -> None:
    """Reset all caches. Call once at the start of each orchestrator run."""
    global _supplier_scales_loaded
    _scout_cache.clear()
    _classification_cache.clear()
    _supplier_scale.clear()
    _supplier_scales_loaded = False


def supplier_scales_loaded() -> bool:
    return _supplier_scales_loaded


# ── Supplier Scout cache ─────────────────────────────────────────────────────

def get_scout(supplier_id: int, product_id: int) -> SupplierEvidence | None:
    return _scout_cache.get((supplier_id, product_id))


def put_scout(supplier_id: int, product_id: int, evidence: SupplierEvidence) -> None:
    _scout_cache[(supplier_id, product_id)] = evidence


# ── Classification cache ─────────────────────────────────────────────────────

def get_classification(product_id: int) -> dict | None:
    return _classification_cache.get(product_id)


def put_classification(product_id: int, cls: dict) -> None:
    _classification_cache[product_id] = cls


def get_all_classifications() -> dict[int, dict]:
    return dict(_classification_cache)


def put_all_classifications(data: dict[int, dict]) -> None:
    _classification_cache.update(data)


# ── Supplier scale cache ─────────────────────────────────────────────────────

def get_supplier_scale(supplier_id: int) -> int:
    return _supplier_scale.get(supplier_id, 0)


def set_supplier_scales(scales: dict[int, int]) -> None:
    global _supplier_scales_loaded
    _supplier_scale.update(scales)
    _supplier_scales_loaded = True
