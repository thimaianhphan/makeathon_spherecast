from functools import reduce
from typing import Callable

from text2product import COMPLIANCE_METRICS  # noqa: F401 — re-exported for callers


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
    compliance: dict[str, tuple] | None = None,
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
    for metric, (lo, hi) in (compliance or {}).items():
        if lo is not None or hi is not None:
            filters.append(quality_metric_filter(metric, lo, hi))
    return filters