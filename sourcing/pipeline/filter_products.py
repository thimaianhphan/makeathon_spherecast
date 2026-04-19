from functools import reduce
from typing import Callable

from text2product import COMPLIANCE_METRICS  # noqa: F401 — re-exported for callers
import db


def filter_products(products: list, filters: list[Callable]) -> list:
    return reduce(lambda acc, f: list(filter(f, acc)), filters, products)


def price_filter(lo=None, hi=None) -> Callable:
    """Passes if any price tier falls within [lo, hi]. Products with no prices pass through."""
    def f(p):
        tiers = p.get("prices") or []
        if not tiers:
            return True
        return any(
            (lo is None or t["price"] >= lo) and (hi is None or t["price"] <= hi)
            for t in tiers
        )
    return f


def quantity_filter(lo=None, hi=None) -> Callable:
    """Passes if any quantity tier falls within [lo, hi]. Products with no quantities pass through."""
    def f(p):
        quantities = [t["quantity"] for t in (p.get("prices") or []) if t.get("quantity") is not None]
        if not quantities:
            return True
        return any((lo is None or q >= lo) and (hi is None or q <= hi) for q in quantities)
    return f


def purity_filter(lo=None, hi=None) -> Callable:
    """Passes if Purity ∈ [0,1] falls within [lo, hi]. Products with no purity pass through."""
    def f(p):
        val = p.get("purity")
        if val is None:
            return True
        return (lo is None or val >= lo) and (hi is None or val <= hi)
    return f


def quality_score_filter(lo=None, hi=None) -> Callable:
    """Passes if QualityScore falls within [lo, hi] (0–1 scale). Products with no score pass through."""
    def f(p):
        val = p.get("quality_score")
        if val is None:
            return True
        return (lo is None or val >= lo) and (hi is None or val <= hi)
    return f


def quality_metric_filter(metric: str, lo=None, hi=None) -> Callable:
    """Passes if p['compliance'][metric] falls within [lo, hi]. Missing values pass through.

    Use lo for minimum-good metrics (identity_confidence, assay_potency, moisture_content).
    Use hi for maximum-limit metrics (heavy_metals, pesticide_residues, residual_solvents).
    microbial_limits: store 0.0 (fail) or 1.0 (pass) and filter with lo=1.0.
    """
    def f(p):
        val = (p.get("compliance") or {}).get(metric)
        if val is None:
            return True
        return (lo is None or val >= lo) and (hi is None or val <= hi)
    return f


# Convenience factory for each metric in COMPLIANCE_METRICS: {metric}_filter(lo, hi).
def _make_metric_filter(metric: str) -> Callable:
    def factory(lo=None, hi=None) -> Callable:
        return quality_metric_filter(metric, lo, hi)
    factory.__name__ = f"{metric}_filter"
    factory.__doc__ = f"{metric}: {COMPLIANCE_METRICS[metric]}"
    return factory

for _metric in COMPLIANCE_METRICS:
    globals()[f"{_metric}_filter"] = _make_metric_filter(_metric)


def make_filters(
    price_range: tuple = (None, None),
    quantity_range: tuple = (None, None),
    purity_range: tuple = (None, None),
    quality_range: tuple = (None, None),
    quality_metrics: dict[str, tuple] | None = None,
) -> list[Callable]:
    """Builds a filter list from range tuples, skipping fully-unbounded ranges.

    compliance maps metric name -> (lo, hi) range, e.g.:
        {
            "identity_confidence": (0.95, None),
            "assay_potency": (0.97, 1.03),
            "heavy_metals": (None, 10.0),
            "pesticide_residues": (None, 100.0),
            "microbial_limits": (1.0, None),
            "moisture_content": (None, 0.05),
            "residual_solvents": (None, 410.0),
        }
    """
    filters = []
    if any(v is not None for v in price_range):
        filters.append(price_filter(*price_range))
    if any(v is not None for v in quantity_range):
        filters.append(quantity_filter(*quantity_range))
    if any(v is not None for v in purity_range):
        filters.append(purity_filter(*purity_range))
    if any(v is not None for v in quality_range):
        filters.append(quality_score_filter(*quality_range))
    for metric, (lo, hi) in (quality_metrics or {}).items():
        if lo is not None or hi is not None:
            filters.append(quality_metric_filter(metric, lo, hi))
    return filters


_DEFAULT_WEIGHTS = {
    "quality_score":       0.40,
    "purity":              0.30,
    "identity_confidence": 0.15,
    "assay_potency":       0.15,
}


def score_product(p: dict, weights: dict | None = None) -> float:
    """Composite score ∈ [0, 1]; returns 0.0 when no data is available."""
    w = weights or _DEFAULT_WEIGHTS
    score, total_w = 0.0, 0.0
    compliance = p.get("compliance") or {}

    for key, wt in w.items():
        if key == "quality_score":
            v = p.get("quality_score")
        elif key == "purity":
            v = p.get("purity")
        elif key == "assay_potency":
            v = compliance.get(key)
            if v is not None:
                v = max(0.0, 1.0 - abs(v - 1.0))
        else:
            v = compliance.get(key)

        if v is not None:
            score   += wt * min(max(v, 0.0), 1.0)
            total_w += wt

    return round(score / total_w, 4) if total_w > 0 else 0.0


def rank_suppliers(
    finished_good_sku: str,
    filters: list | None = None,
    weights: dict | None = None,
) -> dict:
    """Assign BOM components to the fewest suppliers, then score each assignment.

    Returns a dict with keys: suppliers, assignments, uncovered, ranked.
    ranked is a list of dicts sorted by score descending.
    """
    batch_result = db.batch(finished_good_sku, filters=filters)
    if not batch_result["assignments"]:
        return {**batch_result, "ranked": []}

    ranked = []
    for sku, detail in batch_result["assignments"].items():
        ranked.append({
            "supplier":      detail["supplier"],
            "sku":           sku,
            "score":         score_product(detail, weights),
            "purity":        detail.get("purity"),
            "quality":       detail.get("quality"),
            "quality_score": detail.get("quality_score"),
            "compliance":    detail.get("compliance") or {},
            "prices":        detail.get("prices") or [],
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {**batch_result, "ranked": ranked}


def compare_batch(
    finished_good_sku: str,
    filters: list | None = None,
    weights: dict | None = None,
) -> list[dict]:
    """Compare original (BOM) suppliers against new batch assignments for a finished good.

    Returns one row per BOM component:
        sku, old_supplier, new_supplier, new_score, new_purity,
        new_quality_score, new_prices, changed (bool)

    Useful for side-by-side review of what batch() changes vs the status quo.
    """
    boms = db.get_boms()
    bom_lookup = {b["ProducedSKU"]: b["BOMId"] for b in boms}
    bom_id = bom_lookup.get(finished_good_sku)
    if bom_id is None:
        return []

    components = db.get_bom_components(bom_id)
    old_supplier_map = {c["ConsumedSKU"]: c["CompanyName"] for c in components}

    result = rank_suppliers(finished_good_sku, filters=filters, weights=weights)
    assignments = result["assignments"]

    rows = []
    for c in components:
        sku = c["ConsumedSKU"]
        detail = assignments.get(sku) or {}
        new_supplier = detail.get("supplier", "— uncovered —")
        rows.append({
            "sku":             sku,
            "old_supplier":    old_supplier_map.get(sku, "N/A"),
            "new_supplier":    new_supplier,
            "new_score":       score_product(detail, weights) if detail else None,
            "new_purity":      detail.get("purity"),
            "new_quality_score": detail.get("quality_score"),
            "new_prices":      detail.get("prices") or [],
            "changed":         old_supplier_map.get(sku) != new_supplier,
        })

    rows.sort(key=lambda r: r["sku"])
    return rows


def print_batch_comparison(rows: list[dict], finished_good_sku: str = "") -> None:
    """Pretty-print the output of compare_batch() as an aligned table."""
    if finished_good_sku:
        print(f"Product : {finished_good_sku}")
    changed = sum(1 for r in rows if r["changed"])
    print(f"Components: {len(rows)}  |  Changed: {changed}  |  "
          f"Uncovered: {sum(1 for r in rows if r['new_supplier'] == '— uncovered —')}\n")

    SKU_W, SUP_W, SCORE_W, PUR_W = 48, 24, 7, 7
    header = (
        f"{'SKU':<{SKU_W}} {'Old Supplier':<{SUP_W}} {'New Supplier':<{SUP_W}} "
        f"{'Score':>{SCORE_W}} {'Purity':>{PUR_W}}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        score = f"{r['new_score']:.3f}" if r["new_score"] is not None else "  N/A "
        purity = f"{r['new_purity']:.3f}" if r["new_purity"] is not None else "  N/A "
        marker = " *" if r["changed"] else ""
        print(
            f"{r['sku']:<{SKU_W}} {r['old_supplier']:<{SUP_W}} "
            f"{r['new_supplier']:<{SUP_W}} {score:>{SCORE_W}} {purity:>{PUR_W}}{marker}"
        )
    if changed:
        print("\n* supplier changed from original BOM")