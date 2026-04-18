"""Tests for retrieval.openfoodfacts — fixture JSON responses."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.retrieval.openfoodfacts import (
    OpenFoodFactsRecord,
    _parse_product,
    _extract_e_number,
    lookup,
    clear_cache,
)

FIXTURE_PRODUCT = {
    "product_name": "Soy Lecithin",
    "allergens_tags": ["en:soybeans"],
    "labels_tags": ["en:no-gmo", "en:vegan"],
    "additives_tags": ["en:e322"],
    "ingredients_text": "Soy lecithin (E322)",
    "nova_group": 1,
    "categories_tags": ["en:emulsifiers", "en:food-additives"],
}

FIXTURE_SEARCH_RESPONSE = {
    "products": [FIXTURE_PRODUCT],
    "count": 1,
    "page": 1,
    "page_size": 3,
}


def test_parse_product_allergens():
    """Allergens are correctly extracted from tags."""
    record = _parse_product("Soy Lecithin", FIXTURE_PRODUCT, source_url="https://example.com")
    assert record.found is True
    assert "soybeans" in record.allergens


def test_parse_product_labels():
    """Labels are normalised from OFF tags."""
    record = _parse_product("Soy Lecithin", FIXTURE_PRODUCT, source_url="https://example.com")
    assert any("gmo" in l for l in record.labels)


def test_parse_product_additives():
    """Additives extracted from additive_tags."""
    record = _parse_product("Soy Lecithin", FIXTURE_PRODUCT, source_url="https://example.com")
    assert any("e322" in a for a in record.additives)


def test_extract_e_number():
    assert _extract_e_number("Lecithin (E322)") == "E322"
    assert _extract_e_number("Xanthan Gum E415") == "E415"
    assert _extract_e_number("Sunflower Oil") is None


@pytest.mark.asyncio
async def test_lookup_returns_parsed_record(monkeypatch):
    """lookup() parses an OpenFoodFacts search response into a typed record."""
    clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=FIXTURE_SEARCH_RESPONSE)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        record = await lookup("Soy Lecithin")

    assert isinstance(record, OpenFoodFactsRecord)
    assert record.found is True
    assert "soybeans" in record.allergens
    assert record.product_name == "Soy Lecithin"


@pytest.mark.asyncio
async def test_lookup_returns_empty_on_no_results(monkeypatch):
    """lookup() returns found=False when OFF returns no products."""
    clear_cache()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value={"products": [], "count": 0})

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        record = await lookup("UnknownIngredient999")

    assert record.found is False
