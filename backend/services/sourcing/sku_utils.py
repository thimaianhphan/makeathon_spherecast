"""
SKU utility helpers for the sourcing pipeline.

Raw-material SKUs are stored as "RM-C<n>-<human-name>-<8hex>" in the DB.
Web searches and LLM prompts need the human-readable portion only.
"""

import re

_SKU_PREFIX = re.compile(r"^RM-C\d+-", re.IGNORECASE)
_SKU_SUFFIX = re.compile(r"-[0-9a-f]{8}$", re.IGNORECASE)


def material_name_from_sku(sku: str) -> str:
    """
    Extract the human-readable material name from a raw-material SKU.

    Examples:
        "RM-C1-calcium-citrate-05c28cc3"           -> "calcium citrate"
        "RM-C12-d-alpha-tocopheryl-succinate-532e67fd" -> "d alpha tocopheryl succinate"
        "RM-C1-titanium-dioxide"  (no suffix hash)  -> "titanium dioxide"
        "calcium citrate"         (already clean)    -> "calcium citrate"
        ""                                           -> ""

    Falls back to the raw SKU if the result would be empty after stripping.
    The function is idempotent: passing an already-clean name returns it unchanged.
    """
    if not sku:
        return ""
    stripped = _SKU_PREFIX.sub("", sku)
    stripped = _SKU_SUFFIX.sub("", stripped)
    stripped = stripped.replace("-", " ").strip()
    # If stripping produced nothing (unlikely), return the original
    return stripped or sku
