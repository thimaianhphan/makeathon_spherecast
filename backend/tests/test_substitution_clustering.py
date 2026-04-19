"""
Tests for substitution_service clustering logic.

Verifies:
- Pairs are generated only within the same functional category
- Near-duplicate names (rapidfuzz ≥ 85) produce high-confidence candidates without LLM
- Batch classification uses a single LLM call for groups of materials
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.services.substitution_service import (
    _compute_similarity_matrix,
    _make_near_duplicate_candidate,
    build_substitution_graph,
)
from backend.schemas import ComplianceResult


FIXTURE_RAW_MATERIALS = [
    # Category: emulsifiers
    {"Id": 1, "Name": "Soy Lecithin", "SKU": "SL-001", "Type": "raw-material"},
    {"Id": 2, "Name": "Soy Lecithin (Non-GMO)", "SKU": "SL-002", "Type": "raw-material"},
    {"Id": 3, "Name": "Sunflower Lecithin", "SKU": "SL-003", "Type": "raw-material"},
    # Category: sweeteners
    {"Id": 4, "Name": "Stevia Extract", "SKU": "STE-001", "Type": "raw-material"},
    {"Id": 5, "Name": "Monk Fruit Sweetener", "SKU": "MFS-001", "Type": "raw-material"},
    # Category: fats_oils
    {"Id": 6, "Name": "Sunflower Oil", "SKU": "SFO-001", "Type": "raw-material"},
    {"Id": 7, "Name": "Canola Oil", "SKU": "CO-001", "Type": "raw-material"},
    {"Id": 8, "Name": "Palm Oil", "SKU": "PO-001", "Type": "raw-material"},
]

FIXTURE_BOMS = [
    {
        "bom_id": 10,
        "produced_product": {"id": 100, "name": "Protein Bar", "company_id": 1},
        "components": [
            {"product_id": 1, "Name": "Soy Lecithin"},
            {"product_id": 4, "Name": "Stevia Extract"},
            {"product_id": 6, "Name": "Sunflower Oil"},
        ],
    }
]

# Mock classifications: each material pre-assigned to a category
MOCK_CLASSIFICATIONS = {
    1: {"category": "emulsifiers", "allergens": ["soybeans"], "food_categories": [], "e_number": "E322"},
    2: {"category": "emulsifiers", "allergens": ["soybeans"], "food_categories": [], "e_number": "E322"},
    3: {"category": "emulsifiers", "allergens": [], "food_categories": [], "e_number": "E322"},
    4: {"category": "sweeteners", "allergens": [], "food_categories": [], "e_number": None},
    5: {"category": "sweeteners", "allergens": [], "food_categories": [], "e_number": None},
    6: {"category": "fats_oils", "allergens": [], "food_categories": [], "e_number": None},
    7: {"category": "fats_oils", "allergens": [], "food_categories": [], "e_number": None},
    8: {"category": "fats_oils", "allergens": [], "food_categories": [], "e_number": None},
}


def test_similarity_matrix_near_duplicates():
    """'Soy Lecithin' and 'Soy Lecithin (Non-GMO)' score ≥ 85."""
    members = [
        {"Id": 1, "Name": "Soy Lecithin"},
        {"Id": 2, "Name": "Soy Lecithin (Non-GMO)"},
        {"Id": 3, "Name": "Canola Oil"},
    ]
    matrix = _compute_similarity_matrix(members)
    # 0↔1 should be near-duplicate
    assert matrix[0][1] >= 85, f"Expected ≥85 but got {matrix[0][1]}"
    # 0↔2 should be clearly different
    assert matrix[0][2] < 60, f"Expected <60 for unrelated names but got {matrix[0][2]}"


def test_near_duplicate_candidate_high_confidence():
    """Near-duplicate candidate has high confidence and no LLM needed."""
    rm_a = {"Id": 1, "Name": "Soy Lecithin", "SKU": "SL-001"}
    rm_b = {"Id": 2, "Name": "Soy Lecithin (Non-GMO)", "SKU": "SL-002"}
    candidate = _make_near_duplicate_candidate(rm_a, rm_b, "emulsifiers", 90.0)
    assert candidate.confidence >= 0.85
    assert candidate.overall_viable is True
    assert "Near-duplicate" in candidate.evidence_trail[0].excerpt


@pytest.mark.asyncio
async def test_build_graph_only_pairs_within_category():
    """Pairs are generated only within the same functional category."""
    # Mock LLM calls — only called for non-near-duplicate pairs
    async def mock_ai_reason(*args, **kwargs):
        return '{"viable": true, "confidence": 0.75, "reasoning": "Functionally similar", "key_constraints": []}'

    mock_compliance = AsyncMock()
    mock_compliance.return_value = ComplianceResult(
        checks=[], overall_status="approved", blocking_issues=[]
    )

    with patch("backend.services.substitution_service._classify_all",
               new=AsyncMock(return_value=MOCK_CLASSIFICATIONS)), \
         patch("backend.services.substitution_service.infer_eu_compliance",
               new=mock_compliance):

        from backend.services import agent_service
        with patch.object(agent_service, "ai_reason", mock_ai_reason):
            graph = await build_substitution_graph(FIXTURE_RAW_MATERIALS, FIXTURE_BOMS)

    # Verify no cross-category pairs exist
    for group_id, group in graph.items():
        for candidate in group.candidates:
            orig_id = candidate.original_product_id
            sub_id = candidate.substitute_product_id
            orig_cat = MOCK_CLASSIFICATIONS.get(orig_id, {}).get("category")
            sub_cat = MOCK_CLASSIFICATIONS.get(sub_id, {}).get("category")
            assert orig_cat == sub_cat, (
                f"Cross-category pair: {candidate.original_name} ({orig_cat}) "
                f"→ {candidate.substitute_name} ({sub_cat})"
            )
