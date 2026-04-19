"""Compliance controller — raw-material compliance checks for a finished good."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.service_compliance_checker import check_product_compliance

router = APIRouter()


@router.get("/api/compliance/{product_id}")
async def get_compliance(
    product_id: int,
    scrape: bool = Query(
        False,
        description="If true, fetch allowlisted supplier websites for live evidence. Slower.",
    ),
):
    """Run the raw-material compliance checker for a finished good."""
    try:
        report = check_product_compliance(
            finished_product_id=product_id,
            scrape=scrape,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "product_id": product_id},
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"error": f"compliance check failed: {exc}", "product_id": product_id},
        )
    return report
