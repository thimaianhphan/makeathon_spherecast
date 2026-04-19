"""
OpenFoodFacts Retrieval — Agnes AI Supply Chain Manager.

Real API integration for ingredient/additive data.
Endpoints used:
  /api/v2/search?search_terms=<name>&fields=...
  /api/v2/product/<barcode>.json  (for known barcodes)
  Additive page: /additive/<e_number_lower>.json  (community knowledge)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from backend.config import OPENFOODFACTS_API_URL, HTTP_TIMEOUT_SECONDS

_cache: dict[str, "OpenFoodFactsRecord"] = {}

OFF_FIELDS = "product_name,allergens_tags,labels_tags,additives_tags,ingredients_text,nova_group,categories_tags"


@dataclass
class OpenFoodFactsRecord:
    query: str
    product_name: str = ""
    allergens: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)       # organic, no-gmo, kosher, halal, etc.
    additives: list[str] = field(default_factory=list)    # e322, e471, etc.
    ingredients_text: str = ""
    nova_group: Optional[int] = None
    categories: list[str] = field(default_factory=list)
    e_number: Optional[str] = None                        # detected from name or additive list
    source_url: str = ""
    found: bool = False


async def lookup(ingredient_name: str) -> OpenFoodFactsRecord:
    """Look up an ingredient/additive on OpenFoodFacts. Cached per session."""
    key = ingredient_name.lower().strip()
    if key in _cache:
        return _cache[key]

    result = await _search(ingredient_name)
    _cache[key] = result

    # Also try additive endpoint if E-number detected
    e_num = _extract_e_number(ingredient_name)
    if e_num and not result.found:
        additive_result = await _fetch_additive(e_num, ingredient_name)
        if additive_result.found:
            _cache[key] = additive_result
            return additive_result

    return result


async def _search(name: str) -> OpenFoodFactsRecord:
    url = f"{OPENFOODFACTS_API_URL}/search"
    params = {
        "search_terms": name,
        "fields": OFF_FIELDS,
        "page_size": 3,
        "json": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return OpenFoodFactsRecord(query=name)
            data = resp.json()
            products = data.get("products", [])
            if not products:
                return OpenFoodFactsRecord(query=name)
            p = products[0]
            return _parse_product(name, p, source_url=f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={name}")
    except Exception:
        return OpenFoodFactsRecord(query=name)


async def _fetch_additive(e_number: str, original_name: str) -> OpenFoodFactsRecord:
    """Fetch additive details from OFF additive page."""
    slug = e_number.lower().replace(" ", "-")
    url = f"https://world.openfoodfacts.org/additive/{slug}.json"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return OpenFoodFactsRecord(query=original_name)
            data = resp.json()
            tag = data.get("tag", {})
            name_val = tag.get("name", {}).get("en", "")
            return OpenFoodFactsRecord(
                query=original_name,
                product_name=name_val or e_number,
                e_number=e_number,
                source_url=url,
                found=bool(name_val),
            )
    except Exception:
        return OpenFoodFactsRecord(query=original_name)


def _parse_product(query: str, p: dict, source_url: str) -> OpenFoodFactsRecord:
    allergens = [a.replace("en:", "").replace("_", " ") for a in p.get("allergens_tags", [])]
    labels = [la.replace("en:", "").replace("-", " ") for la in p.get("labels_tags", [])]
    additives = [a.replace("en:", "") for a in p.get("additives_tags", [])]
    categories = [c.replace("en:", "").replace("-", " ") for c in (p.get("categories_tags") or [])[:5]]
    nova = p.get("nova_group")
    e_num = _extract_e_number(query) or (additives[0] if additives else None)
    return OpenFoodFactsRecord(
        query=query,
        product_name=p.get("product_name", ""),
        allergens=allergens,
        labels=labels,
        additives=additives,
        ingredients_text=(p.get("ingredients_text") or "")[:300],
        nova_group=int(nova) if nova else None,
        categories=categories,
        e_number=e_num,
        source_url=source_url,
        found=True,
    )


def _extract_e_number(name: str) -> Optional[str]:
    m = re.search(r"\bE\d{3,4}[a-z]?\b", name, re.IGNORECASE)
    return m.group(0).upper() if m else None


def clear_cache() -> None:
    _cache.clear()
