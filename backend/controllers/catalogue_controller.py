"""Catalogue controller — finished-good product listing from SQLite."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.services.catalogue_service import catalogue_service

router = APIRouter()


@router.get("/api/catalogue")
async def list_catalogue():
    """List all finished-good products from the database."""
    return catalogue_service.list_all()


@router.get("/api/finished-goods")
async def list_finished_goods():
    """Compatibility alias for finished-good listing used by the redesign frontend."""
    return catalogue_service.list_all()


@router.get("/api/catalogue/{product_id}")
async def get_product(product_id: str):
    """Get single product by ID."""
    product = catalogue_service.get(product_id)
    if not product:
        return JSONResponse(status_code=404, content={"error": "Product not found"})
    return product
