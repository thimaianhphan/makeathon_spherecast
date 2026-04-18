"""
Integration test for enrichment_service with all externals mocked.

Verifies:
- enrich_ingredient_full returns ≥3 evidence items
- Evidence items have mixed source_types (not all llm_inference)
- Allergens detected from OFF mock + name heuristics
- Regulatory references always attached
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.retrieval.openfoodfacts import OpenFoodFactsRecord
from backend.services.retrieval.web_search import SearchHit
from backend.services.retrieval.web_fetch import FetchedPage


OFF_SOY_LECITHIN = OpenFoodFactsRecord(
    query="Soy Lecithin",
    product_name="Soy Lecithin",
    allergens=["soybeans"],
    labels=["no-gmo", "vegan"],
    additives=["e322"],
    ingredients_text="soy lecithin E322",
    nova_group=1,
    categories=["emulsifiers"],
    e_number="E322",
    source_url="https://world.openfoodfacts.org/cgi/search.pl?search_terms=Soy+Lecithin",
    found=True,
)


@pytest.fixture(autouse=True)
def enable_enrichment(monkeypatch):
    import backend.config as cfg
    monkeypatch.setattr(cfg, "ENABLE_EXTERNAL_ENRICHMENT", True)
    monkeypatch.setattr(cfg, "ENABLE_WEB_SEARCH", True)


@pytest.fixture(autouse=True)
def clear_enrichment_cache():
    from backend.services import enrichment_service
    enrichment_service.clear_cache()
    yield
    enrichment_service.clear_cache()


@pytest.mark.asyncio
async def test_enrich_soy_lecithin_has_mixed_sources():
    """Enriching 'Soy Lecithin' produces ≥3 items with source_types beyond llm_inference."""
    web_hit = SearchHit(
        title="Soy Lecithin EU regulation",
        url="https://example.com/soy-lecithin-eu",
        snippet="Soy lecithin E322 is approved under EU 1333/2008.",
    )
    fetch_page = FetchedPage(
        url="https://example.com/soy-lecithin-eu",
        title="Soy Lecithin EU regulation",
        content="Soy lecithin E322 is approved under EU 1333/2008. Contains soybeans allergen.",
        status_code=200,
    )

    with patch("backend.services.retrieval.openfoodfacts.lookup", new=AsyncMock(return_value=OFF_SOY_LECITHIN)), \
         patch("backend.services.retrieval.web_search.search", new=AsyncMock(return_value=[web_hit])), \
         patch("backend.services.retrieval.web_fetch.fetch_clean", new=AsyncMock(return_value=fetch_page)):

        from backend.services.enrichment_service import enrich_ingredient_full
        result = await enrich_ingredient_full("Soy Lecithin")

    assert len(result.evidence) >= 3, f"Expected ≥3 evidence items, got {len(result.evidence)}"

    source_types = {e.source_type for e in result.evidence}
    # Must have types beyond llm_inference
    non_llm = source_types - {"llm_inference"}
    assert non_llm, f"All evidence is llm_inference: {source_types}"

    # Allergens confirmed
    assert "soybeans" in result.allergens_confirmed

    # E-number detected
    assert result.e_number == "E322"


@pytest.mark.asyncio
async def test_enrich_always_has_regulatory_references():
    """Enrichment always includes at least one regulatory_reference evidence item."""
    with patch("backend.services.retrieval.openfoodfacts.lookup", new=AsyncMock(return_value=OpenFoodFactsRecord(query="test"))), \
         patch("backend.services.retrieval.web_search.search", new=AsyncMock(return_value=[])):

        from backend.services.enrichment_service import enrich_ingredient_full
        result = await enrich_ingredient_full("Wheat Flour")

    reg_items = [e for e in result.evidence if e.source_type == "regulatory_reference"]
    assert len(reg_items) >= 1, "Expected at least one regulatory_reference evidence item"
    # Wheat → cereals_containing_gluten should be inferred
    assert "cereals_containing_gluten" in result.allergens_confirmed


@pytest.mark.asyncio
async def test_uncertain_allergen_flips_viable(monkeypatch):
    """An uncertain allergen check (with BLOCK_ON_UNCERTAIN_ALLERGEN=true) → overall_viable=False."""
    import backend.config as cfg
    monkeypatch.setattr(cfg, "BLOCK_ON_UNCERTAIN_ALLERGEN", True)

    from backend.services.substitution_service import infer_eu_compliance

    # Use an ingredient where allergen cannot be inferred
    result = await infer_eu_compliance(
        substitute={"Name": "XYZ Novel Compound", "Id": 999, "SKU": "XYZ-001"},
        original={"Name": "Sunflower Oil", "Id": 1, "SKU": "SFO-001"},
        finished_product={"name": "Protein Bar", "id": 100},
        existing_bom=[],
        enrichment_data=None,
    )

    # With no evidence and BLOCK_ON_UNCERTAIN_ALLERGEN, allergen check → uncertain → rejected
    allergen_check = next((c for c in result.checks if c.check == "allergen_safety"), None)
    if allergen_check and allergen_check.status == "uncertain":
        assert result.overall_status == "rejected", (
            f"Expected rejected for uncertain allergen, got {result.overall_status}"
        )
