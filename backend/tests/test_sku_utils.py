"""
Unit tests for backend.services.sourcing.sku_utils.material_name_from_sku
"""

import pytest
from backend.services.sourcing.sku_utils import material_name_from_sku


@pytest.mark.parametrize("sku, expected", [
    # Standard SKU with prefix + suffix hash
    ("RM-C1-calcium-citrate-05c28cc3", "calcium citrate"),
    # Longer category index, multi-segment name
    ("RM-C2-d-alpha-tocopheryl-succinate-532e67fd", "d alpha tocopheryl succinate"),
    # Two-digit category index
    ("RM-C12-soy-lecithin-cc38c49d", "soy lecithin"),
    # Empty string must return empty string (not the raw value)
    ("", ""),
    # Already-clean name — function must be idempotent
    ("calcium citrate", "calcium citrate"),
    # Missing suffix hash — still extracts the name correctly
    ("RM-C1-titanium-dioxide", "titanium dioxide"),
    # Mixed-case prefix
    ("rm-c3-magnesium-stearate-ab12cd34", "magnesium stearate"),
    # Single-word name
    ("RM-C5-maltodextrin-deadbeef", "maltodextrin"),
    # Name with many segments
    ("RM-C99-medium-chain-triglycerides-01234567", "medium chain triglycerides"),
])
def test_material_name_from_sku(sku, expected):
    assert material_name_from_sku(sku) == expected
