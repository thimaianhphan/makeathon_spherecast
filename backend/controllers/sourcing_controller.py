"""Sourcing batch controller — wraps the greedy set-cover pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_SOURCING = Path(__file__).resolve().parent.parent.parent / "sourcing" / "pipeline"
if str(_SOURCING) not in sys.path:
    sys.path.insert(0, str(_SOURCING))

from db import batch, get_boms, get_bom_components, get_supplier_products_enriched  # noqa: E402
from filter_products import make_filters  # noqa: E402

router = APIRouter()


class BatchRequest(BaseModel):
    sku: str
    price_min: float | None = None
    price_max: float | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    purity_min: float | None = None
    quality_min: float | None = None
    include_incomplete: bool = False
    n_alternatives: int = 3


def _exclude_suppliers(names: set[str]):
    return lambda p: p.get("supplier_name") not in names


def _metrics(result: dict, total_skus: int) -> dict:
    assignments = result["assignments"]
    scores = [v.get("quality_score") for v in assignments.values() if v.get("quality_score") is not None]
    prices = []
    for v in assignments.values():
        tiers = v.get("prices") or []
        if tiers:
            prices.append(min(t["price"] for t in tiers))
    return {
        "supplier_count": len(result["suppliers"]),
        "covered": len(assignments),
        "uncovered_count": len(result["uncovered"]),
        "coverage_pct": round(len(assignments) / total_skus * 100) if total_skus else 0,
        "avg_quality": round(sum(scores) / len(scores), 3) if scores else None,
        "total_min_cost": round(sum(prices), 2) if prices else None,
    }


def _build_alternative(sku: str, base_filters: list | None, excluded: set[str]) -> dict:
    filters = list(base_filters or [])
    if excluded:
        filters.append(_exclude_suppliers(excluded))
    return batch(sku, filters=filters or None)


@router.get("/api/sourcing/bom/{sku:path}")
async def get_bom(sku: str):
    """Return BOM components with per-component min/max stats from the supplier DB."""
    try:
        boms = get_boms()
        bom = next((b for b in boms if b["ProducedSKU"] == sku), None)
        if not bom:
            return JSONResponse(status_code=404, content={"error": "BOM not found"})
        components = get_bom_components(bom["BOMId"])
        component_skus = {c["ConsumedSKU"] for c in components}

        # aggregate min/max per SKU across all suppliers
        stats: dict[str, dict] = {s: {
            "prices": [], "purities": [], "qualities": []
        } for s in component_skus}

        for p in get_supplier_products_enriched():
            if p["sku"] not in stats:
                continue
            s = stats[p["sku"]]
            for t in p.get("prices") or []:
                if t.get("price") is not None:
                    s["prices"].append(t["price"])
            if p.get("purity") is not None:
                s["purities"].append(p["purity"])
            if p.get("quality_score") is not None:
                s["qualities"].append(p["quality_score"])

        def _range(vals: list) -> dict:
            if not vals:
                return {"min": None, "max": None}
            return {"min": round(min(vals), 4), "max": round(max(vals), 4)}

        return [
            {
                "sku": c["ConsumedSKU"],
                "type": c["Type"],
                "stats": {
                    "price": _range(stats[c["ConsumedSKU"]]["prices"]),
                    "purity": _range(stats[c["ConsumedSKU"]]["purities"]),
                    "quality": _range(stats[c["ConsumedSKU"]]["qualities"]),
                },
            }
            for c in components
        ]
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.get("/api/sourcing/boms")
async def list_boms():
    """List all finished-good SKUs that have BOMs in the sourcing database."""
    try:
        boms = get_boms()
        return [{"sku": b["ProducedSKU"], "company": b["CompanyName"]} for b in boms]
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@router.post("/api/sourcing/batch")
async def run_batch(req: BatchRequest) -> Any:
    """Run greedy set-cover and return up to n_alternatives supplier combinations."""
    try:
        base_filters = make_filters(
            price_range=(req.price_min, req.price_max),
            quantity_range=(req.quantity_min, req.quantity_max),
            purity_range=(req.purity_min, None),
            quality_range=(req.quality_min, None),
        ) if any([req.price_min, req.price_max, req.quantity_min,
                  req.quantity_max, req.purity_min, req.quality_min]) else None

        # count total BOM skus for coverage %
        boms = get_boms()
        bom = next((b for b in boms if b["ProducedSKU"] == req.sku), None)
        total_skus = len(get_bom_components(bom["BOMId"])) if bom else 0

        alternatives = []
        excluded: set[str] = set()

        for _ in range(req.n_alternatives):
            result = _build_alternative(req.sku, base_filters, excluded)
            is_complete = len(result["uncovered"]) == 0

            if not result["assignments"]:
                break  # no coverage possible at all

            if not is_complete and not req.include_incomplete:
                # Can't find a complete alternative — stop rather than keep excluding
                break

            metrics = _metrics(result, total_skus)
            assignments = [
                {
                    "sku": sku,
                    "supplier": info.get("supplier"),
                    "purity": info.get("purity"),
                    "quality_score": info.get("quality_score"),
                    "prices": info.get("prices") or [],
                }
                for sku, info in result["assignments"].items()
            ]
            alternatives.append({
                "suppliers": result["suppliers"],
                "assignments": assignments,
                "uncovered": result["uncovered"],
                "metrics": metrics,
            })

            # Exclude this alternative's top supplier to force a different combination next
            if result["suppliers"]:
                excluded.add(result["suppliers"][0])

        # compute deltas relative to alternative 0
        if alternatives:
            base = alternatives[0]["metrics"]
            for alt in alternatives:
                m = alt["metrics"]
                alt["deltas"] = {
                    "supplier_count": m["supplier_count"] - base["supplier_count"],
                    "avg_quality": round(
                        (m["avg_quality"] or 0) - (base["avg_quality"] or 0), 3
                    ) if m["avg_quality"] is not None and base["avg_quality"] is not None else None,
                    "total_min_cost": round(
                        (m["total_min_cost"] or 0) - (base["total_min_cost"] or 0), 2
                    ) if m["total_min_cost"] is not None and base["total_min_cost"] is not None else None,
                }

        return {"sku": req.sku, "alternatives": alternatives}

    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
