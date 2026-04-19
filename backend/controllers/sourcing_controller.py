"""Sourcing batch controller — wraps the greedy set-cover pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# make sourcing pipeline importable
_SOURCING = Path(__file__).resolve().parent.parent.parent / "sourcing" / "pipeline"
if str(_SOURCING) not in sys.path:
    sys.path.insert(0, str(_SOURCING))

from db import batch, get_boms  # noqa: E402
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
    """Run greedy set-cover batching for a finished-good SKU with optional filters."""
    try:
        filters = make_filters(
            price_range=(req.price_min, req.price_max),
            quantity_range=(req.quantity_min, req.quantity_max),
            purity_range=(req.purity_min, None),
            quality_range=(req.quality_min, None),
        ) if any([
            req.price_min, req.price_max,
            req.quantity_min, req.quantity_max,
            req.purity_min, req.quality_min,
        ]) else None

        result = batch(req.sku, filters=filters)

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
        return {
            "sku": req.sku,
            "suppliers": result["suppliers"],
            "assignments": assignments,
            "uncovered": result["uncovered"],
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
