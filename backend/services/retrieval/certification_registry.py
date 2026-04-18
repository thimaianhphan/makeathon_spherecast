"""
Certification Registry — Agnes AI Supply Chain Manager.

Lightweight lookups for public certification registries:
- USDA Organic Integrity Database
- OU Kosher company search
- Non-GMO Project (search page)

Architecture: each registry is an async lookup returning CertificationRecord.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from backend.config import HTTP_TIMEOUT_SECONDS
from backend.time_utils import utc_now_iso

_cache: dict[str, list["CertificationRecord"]] = {}


@dataclass
class CertificationRecord:
    body: str           # e.g. "USDA Organic", "OU Kosher", "Non-GMO Project"
    entity_name: str    # company or product name from registry
    status: str         # "certified" | "not_found" | "expired"
    verified_at: str    # ISO date
    source_url: str
    notes: str = ""


async def lookup_usda_organic(entity_name: str) -> list[CertificationRecord]:
    """Search USDA Organic Integrity Database for entity_name."""
    cache_key = f"usda_organic|{entity_name.lower()}"
    if cache_key in _cache:
        return _cache[cache_key]

    results: list[CertificationRecord] = []
    try:
        # USDA Organic Integrity Database API
        url = "https://organic.ams.usda.gov/Organic/api/CertifiedOperation/GetCertifiedOperationList"
        params = {"searchText": entity_name, "pageNumber": 1, "pageSize": 5}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                operations = data.get("certifiedOperations", data if isinstance(data, list) else [])
                for op in operations[:3]:
                    name = op.get("businessName", op.get("name", ""))
                    status = op.get("certificateStatus", "certified")
                    results.append(CertificationRecord(
                        body="USDA Organic",
                        entity_name=name,
                        status=status.lower() if status else "certified",
                        verified_at=utc_now_iso(),
                        source_url="https://organic.ams.usda.gov/Organic/Certificates",
                        notes=f"Operation type: {op.get('operationType', 'N/A')}",
                    ))
    except Exception:
        pass

    if not results:
        # Fallback: record not-found
        results.append(CertificationRecord(
            body="USDA Organic",
            entity_name=entity_name,
            status="not_found",
            verified_at=utc_now_iso(),
            source_url="https://organic.ams.usda.gov/Organic/Certificates",
        ))

    _cache[cache_key] = results
    return results


async def lookup_ou_kosher(entity_name: str) -> list[CertificationRecord]:
    """Search OU Kosher company database."""
    cache_key = f"ou_kosher|{entity_name.lower()}"
    if cache_key in _cache:
        return _cache[cache_key]

    results: list[CertificationRecord] = []
    try:
        # OU Kosher search endpoint
        url = "https://oukosher.org/passover-products/search/"
        params = {"q": entity_name}
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": "Agnes-Supply-Chain-Bot/1.0"},
        ) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200 and entity_name.lower() in resp.text.lower():
                results.append(CertificationRecord(
                    body="OU Kosher",
                    entity_name=entity_name,
                    status="certified",
                    verified_at=utc_now_iso(),
                    source_url=f"https://oukosher.org/passover-products/search/?q={entity_name}",
                    notes="Found in OU Kosher search results",
                ))
    except Exception:
        pass

    if not results:
        results.append(CertificationRecord(
            body="OU Kosher",
            entity_name=entity_name,
            status="not_found",
            verified_at=utc_now_iso(),
            source_url="https://oukosher.org/passover-products/search/",
        ))

    _cache[cache_key] = results
    return results


async def lookup_non_gmo(entity_name: str) -> list[CertificationRecord]:
    """Search Non-GMO Project verified product database."""
    cache_key = f"non_gmo|{entity_name.lower()}"
    if cache_key in _cache:
        return _cache[cache_key]

    results: list[CertificationRecord] = []
    try:
        url = "https://www.nongmoproject.org/find-non-gmo/search-product-list/"
        params = {"product": entity_name}
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": "Agnes-Supply-Chain-Bot/1.0"},
        ) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200 and entity_name.lower() in resp.text.lower():
                results.append(CertificationRecord(
                    body="Non-GMO Project",
                    entity_name=entity_name,
                    status="certified",
                    verified_at=utc_now_iso(),
                    source_url=f"https://www.nongmoproject.org/find-non-gmo/search-product-list/?product={entity_name}",
                    notes="Found in Non-GMO Project verified list",
                ))
    except Exception:
        pass

    if not results:
        results.append(CertificationRecord(
            body="Non-GMO Project",
            entity_name=entity_name,
            status="not_found",
            verified_at=utc_now_iso(),
            source_url="https://www.nongmoproject.org/find-non-gmo/",
        ))

    _cache[cache_key] = results
    return results


async def lookup_all(entity_name: str) -> list[CertificationRecord]:
    """Run all registry lookups in parallel."""
    import asyncio
    results_groups = await asyncio.gather(
        lookup_usda_organic(entity_name),
        lookup_ou_kosher(entity_name),
        lookup_non_gmo(entity_name),
        return_exceptions=True,
    )
    combined: list[CertificationRecord] = []
    for group in results_groups:
        if isinstance(group, list):
            combined.extend(group)
    return combined


def clear_cache() -> None:
    _cache.clear()
