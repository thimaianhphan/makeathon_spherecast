"""
Supplier Site Retrieval — Agnes AI Supply Chain Manager.

Searches for and fetches supplier product/certification pages.
Returns structured SupplierEvidence with carries/certifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.time_utils import utc_now_iso
from backend.services.retrieval.web_search import search
from backend.services.retrieval.web_fetch import fetch_clean

_cache: dict[str, "SupplierEvidence"] = {}

CERT_KEYWORDS = [
    "kosher", "halal", "organic", "non-gmo", "non gmo", "gmo-free",
    "fssc 22000", "fssc22000", "iso 22000", "iso22000", "brc", "sqf",
    "allergen-free", "allergen free", "gluten-free", "gluten free",
    "vegan", "rainforest alliance", "fair trade", "fairtrade",
]

CARRIES_POSITIVE = ["available", "in stock", "supply", "supplier of", "we offer", "product page", "buy", "order"]
CARRIES_NEGATIVE = ["discontinued", "not available", "out of stock", "no longer"]


@dataclass
class SupplierEvidence:
    supplier_name: str
    material_name: str
    carries: str = "unclear"  # "yes" | "no" | "unclear"
    certifications_mentioned: list[str] = field(default_factory=list)
    source_url: str = ""
    excerpt: str = ""
    confidence: float = 0.4
    retrieved_at: str = ""


async def find_supplier_for_material(supplier_name: str, material_name: str) -> SupplierEvidence:
    """Search for evidence that a supplier carries a material."""
    cache_key = f"{supplier_name.lower()}|{material_name.lower()}"
    if cache_key in _cache:
        return _cache[cache_key]

    result = await _lookup(supplier_name, material_name)
    _cache[cache_key] = result
    return result


async def _lookup(supplier_name: str, material_name: str) -> SupplierEvidence:
    evidence = SupplierEvidence(
        supplier_name=supplier_name,
        material_name=material_name,
        retrieved_at=utc_now_iso(),
    )

    # Search query: supplier + material
    query = f'"{supplier_name}" "{material_name}" food ingredient supplier'
    hits = await search(query, max_results=3)

    best_excerpt = ""
    best_url = ""
    best_carries = "unclear"
    best_certs: list[str] = []

    for hit in hits:
        if not hit.url:
            continue
        page = await fetch_clean(hit.url)
        if page.error or not page.content:
            # Fall back to snippet
            text = hit.snippet.lower()
        else:
            text = page.content.lower()

        certs = _extract_certs(text)
        carries = _detect_carries(text, material_name)

        if carries == "yes" or (carries == "unclear" and best_carries == "unclear"):
            best_carries = carries
            best_excerpt = (hit.snippet or page.content[:300]).strip()
            best_url = hit.url
            best_certs = certs

        if carries == "yes":
            break

    # Also run a certifications-focused search
    cert_query = f'"{supplier_name}" certifications food safety kosher halal organic'
    cert_hits = await search(cert_query, max_results=2)
    for hit in cert_hits:
        if not hit.url:
            continue
        page = await fetch_clean(hit.url)
        text = (page.content or hit.snippet or "").lower()
        best_certs = list(set(best_certs + _extract_certs(text)))

    evidence.carries = best_carries
    evidence.certifications_mentioned = best_certs
    evidence.source_url = best_url
    evidence.excerpt = best_excerpt[:400]
    evidence.confidence = 0.65 if best_carries == "yes" else 0.35

    return evidence


def _extract_certs(text: str) -> list[str]:
    found = []
    for kw in CERT_KEYWORDS:
        if kw in text:
            found.append(kw)
    return found


def _detect_carries(text: str, material_name: str) -> str:
    mat_lower = material_name.lower()
    if mat_lower not in text:
        return "unclear"
    context_window = 200
    idx = text.find(mat_lower)
    context = text[max(0, idx - context_window): idx + context_window]
    for neg in CARRIES_NEGATIVE:
        if neg in context:
            return "no"
    for pos in CARRIES_POSITIVE:
        if pos in context:
            return "yes"
    return "unclear"


def clear_cache() -> None:
    _cache.clear()
