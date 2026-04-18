"""
External Enrichment Service — Agnes AI Supply Chain Manager.

Orchestrates the retrieval package to build multi-source evidence trails
for ingredients and suppliers. Every claim is backed by a traceable EvidenceItem.

Sources (in order of richness):
  1. OpenFoodFacts — allergen/additive/label data
  2. Web search + fetch — contextual regulatory and product pages
  3. Curated regulatory citations (EUR-Lex / EFSA)
  4. Supplier site search — carries + certifications
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Optional

from backend.config import ENABLE_EXTERNAL_ENRICHMENT
from backend.schemas import EvidenceItem
from backend.services import evidence_store
from backend.services.retrieval import openfoodfacts, regulatory, web_search, web_fetch, supplier_site

# Session cache keyed by ingredient/supplier name
_enrichment_cache: dict[str, "EnrichmentResult"] = {}
_supplier_cache: dict[str, "SupplierEnrichment"] = {}


class EnrichmentResult:
    def __init__(
        self,
        ingredient: str,
        allergens_confirmed: list[str],
        organic_certified: Optional[bool],
        gmo_status: Optional[str],
        e_number: Optional[str],
        confidence_delta: float,
        evidence: list[EvidenceItem],
        summary: str,
    ):
        self.ingredient = ingredient
        self.allergens_confirmed = allergens_confirmed
        self.organic_certified = organic_certified
        self.gmo_status = gmo_status
        self.e_number = e_number
        self.confidence_delta = round(min(1.0, confidence_delta), 3)
        self.evidence = evidence
        self.summary = summary

    def to_legacy_dict(self) -> dict:
        """Backwards-compatible dict for code that expects the old enrichment dict."""
        return {
            "ingredient": self.ingredient,
            "e_number": self.e_number,
            "allergens_confirmed": self.allergens_confirmed,
            "organic_certified": self.organic_certified,
            "regulatory_references": [
                {"source": e.source_type, "url": e.source_url, "excerpt": e.excerpt[:200]}
                for e in self.evidence
                if e.source_type in ("regulatory_reference", "external_api")
            ],
            "confidence_upgrade": self.confidence_delta,
            "source": "enriched" if self.evidence else "not_enriched",
        }


class SupplierEnrichment:
    def __init__(
        self,
        supplier_name: str,
        certifications: list[str],
        carries_materials: dict[str, str],  # material_name → "yes" | "no" | "unclear"
        evidence: list[EvidenceItem],
    ):
        self.supplier_name = supplier_name
        self.certifications = certifications
        self.carries_materials = carries_materials
        self.evidence = evidence


async def enrich_ingredient(ingredient_name: str) -> dict:
    """
    Enrich ingredient with multi-source evidence. Returns legacy-compatible dict.
    Side-effect: records EvidenceItems in evidence_store.
    """
    if not ENABLE_EXTERNAL_ENRICHMENT:
        return _empty_enrichment(ingredient_name)

    cache_key = ingredient_name.lower().strip()
    if cache_key in _enrichment_cache:
        return _enrichment_cache[cache_key].to_legacy_dict()

    result = await _enrich(ingredient_name)
    _enrichment_cache[cache_key] = result
    for ev in result.evidence:
        evidence_store.record(ev)
    return result.to_legacy_dict()


async def enrich_ingredient_full(ingredient_name: str) -> EnrichmentResult:
    """Return the full EnrichmentResult (used by compliance step)."""
    if not ENABLE_EXTERNAL_ENRICHMENT:
        return EnrichmentResult(
            ingredient=ingredient_name,
            allergens_confirmed=[],
            organic_certified=None,
            gmo_status=None,
            e_number=None,
            confidence_delta=0.0,
            evidence=[],
            summary="Enrichment disabled",
        )

    cache_key = ingredient_name.lower().strip()
    if cache_key in _enrichment_cache:
        return _enrichment_cache[cache_key]

    result = await _enrich(ingredient_name)
    _enrichment_cache[cache_key] = result
    for ev in result.evidence:
        evidence_store.record(ev)
    return result


async def enrich_supplier(
    supplier_name: str,
    material_names: Optional[list[str]] = None,
) -> dict:
    """Enrich supplier data from public sources. Returns dict for backwards compat."""
    if not ENABLE_EXTERNAL_ENRICHMENT:
        return {"supplier": supplier_name, "certifications": [], "confidence_upgrade": 0.0}

    cache_key = supplier_name.lower().strip()
    if cache_key in _supplier_cache:
        enrichment = _supplier_cache[cache_key]
    else:
        enrichment = await _enrich_supplier(supplier_name, material_names or [])
        _supplier_cache[cache_key] = enrichment
        for ev in enrichment.evidence:
            evidence_store.record(ev)

    return {
        "supplier": enrichment.supplier_name,
        "certifications": enrichment.certifications,
        "carries_materials": enrichment.carries_materials,
        "confidence_upgrade": 0.2 if enrichment.certifications else 0.0,
        "source": "enriched",
        "evidence_ids": [ev.evidence_id for ev in enrichment.evidence],
    }


async def enrich_supplier_full(
    supplier_name: str,
    material_names: Optional[list[str]] = None,
) -> SupplierEnrichment:
    cache_key = supplier_name.lower().strip()
    if cache_key in _supplier_cache:
        return _supplier_cache[cache_key]
    result = await _enrich_supplier(supplier_name, material_names or [])
    _supplier_cache[cache_key] = result
    for ev in result.evidence:
        evidence_store.record(ev)
    return result


def clear_cache() -> None:
    _enrichment_cache.clear()
    _supplier_cache.clear()


# ── Core enrichment logic ────────────────────────────────────────────────────

async def _enrich(name: str) -> EnrichmentResult:
    evidence: list[EvidenceItem] = []
    allergens: list[str] = []
    organic: Optional[bool] = None
    gmo_status: Optional[str] = None
    confidence_delta = 0.0
    e_number: Optional[str] = None
    now = datetime.utcnow().isoformat() + "Z"

    # 1. OpenFoodFacts
    off_record = await openfoodfacts.lookup(name)
    if off_record.found:
        allergens = list({
            _normalise_allergen(a) for a in off_record.allergens if a
        })
        organic = _labels_to_organic(off_record.labels)
        gmo_status = _labels_to_gmo(off_record.labels)
        e_number = off_record.e_number
        confidence_delta += 0.25
        ev = EvidenceItem(
            source_type="external_api",
            source_url=off_record.source_url,
            source_title=f"OpenFoodFacts: {off_record.product_name or name}",
            excerpt=(
                f"Allergens: {off_record.allergens or 'none declared'}. "
                f"Labels: {off_record.labels[:5] or 'none'}. "
                f"Additives: {off_record.additives[:5] or 'none'}."
            )[:500],
            confidence=0.80,
            timestamp=now,
            retrieved_at=now,
            claim=f"Allergen/additive profile of {name}",
        )
        evidence.append(ev)

    # 2. Name-based allergen heuristics (fast, no network)
    heuristic_allergens = _heuristic_allergens(name)
    for ha in heuristic_allergens:
        if ha not in allergens:
            allergens.append(ha)
            confidence_delta += 0.1
    if heuristic_allergens:
        evidence.append(EvidenceItem(
            source_type="llm_inference",
            excerpt=f"Allergen heuristic from name '{name}': {heuristic_allergens}",
            confidence=0.70,
            timestamp=now,
            claim=f"Name-based allergen inference for {name}",
        ))

    # 3. Regulatory reference for detected E-number
    if e_number:
        reg_ev = regulatory.get_additive_evidence(e_number, claim=f"EU approval of {e_number} in {name}")
        if reg_ev:
            evidence.append(reg_ev)
            confidence_delta += 0.15

    # 4. Regulatory references for allergen and additive regulations
    reg_ev_allergen = regulatory.get_regulation_evidence(
        "EU 1169/2011", claim=f"Allergen labelling obligation for {name}"
    )
    if reg_ev_allergen:
        evidence.append(reg_ev_allergen)

    reg_ev_additive = regulatory.get_regulation_evidence(
        "EU 1333/2008", claim=f"Additive approval regime applicable to {name}"
    )
    if reg_ev_additive:
        evidence.append(reg_ev_additive)

    # 5. Web search for additional context (allergens, regulatory)
    search_query = f"{name} food additive EU allergen regulation"
    hits = await web_search.search(search_query, max_results=3)
    for hit in hits[:2]:
        if not hit.url:
            continue
        page = await web_fetch.fetch_clean(hit.url)
        text = page.content or hit.snippet
        if not text:
            continue
        confidence_delta += 0.05
        evidence.append(EvidenceItem(
            source_type="web_search",
            source_url=hit.url,
            source_title=hit.title,
            excerpt=text[:400],
            confidence=0.55,
            timestamp=now,
            retrieved_at=now,
            claim=f"Web evidence for {name} allergen/regulatory status",
        ))
        break  # one web evidence item is enough

    # 6. Organic status from name
    if organic is None:
        organic = _infer_organic(name)

    summary = (
        f"Allergens: {allergens or 'none confirmed'}. "
        f"Organic: {organic}. GMO: {gmo_status or 'unknown'}. "
        f"E-number: {e_number or 'none'}. "
        f"Evidence items: {len(evidence)}."
    )

    return EnrichmentResult(
        ingredient=name,
        allergens_confirmed=allergens,
        organic_certified=organic,
        gmo_status=gmo_status,
        e_number=e_number,
        confidence_delta=confidence_delta,
        evidence=evidence,
        summary=summary,
    )


async def _enrich_supplier(supplier_name: str, material_names: list[str]) -> SupplierEnrichment:
    evidence: list[EvidenceItem] = []
    carries: dict[str, str] = {}
    certs: list[str] = []
    now = datetime.utcnow().isoformat() + "Z"

    # Look up each material (up to 3 to bound requests)
    tasks = [
        supplier_site.find_supplier_for_material(supplier_name, mat)
        for mat in material_names[:3]
    ]
    sup_results = await asyncio.gather(*tasks, return_exceptions=True)

    for mat, result in zip(material_names[:3], sup_results):
        if isinstance(result, Exception):
            carries[mat] = "unclear"
            continue
        carries[mat] = result.carries
        certs.extend(result.certifications_mentioned)
        if result.source_url and result.excerpt:
            evidence.append(EvidenceItem(
                source_type="supplier_website",
                source_url=result.source_url,
                source_title=f"{supplier_name} — {mat}",
                excerpt=result.excerpt[:400],
                confidence=result.confidence,
                timestamp=now,
                retrieved_at=now,
                claim=f"Supplier {supplier_name} carries {mat}",
            ))

    certs = list(set(certs))

    return SupplierEnrichment(
        supplier_name=supplier_name,
        certifications=certs,
        carries_materials=carries,
        evidence=evidence,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalise_allergen(tag: str) -> str:
    mapping = {
        "gluten": "cereals_containing_gluten",
        "wheat": "cereals_containing_gluten",
        "rye": "cereals_containing_gluten",
        "barley": "cereals_containing_gluten",
        "oat": "cereals_containing_gluten",
        "soy": "soybeans",
        "soya": "soybeans",
        "dairy": "milk",
        "lactose": "milk",
        "casein": "milk",
        "whey": "milk",
        "nut": "nuts",
        "almond": "nuts",
        "walnut": "nuts",
        "hazelnut": "nuts",
        "sulphite": "sulphur_dioxide_sulphites",
        "sulfite": "sulphur_dioxide_sulphites",
        "sulphur dioxide": "sulphur_dioxide_sulphites",
    }
    tag = tag.strip().lower()
    return mapping.get(tag, tag.replace("-", "_").replace(" ", "_"))


def _heuristic_allergens(name: str) -> list[str]:
    name_lower = name.lower()
    found = []
    checks = [
        (["soy", "soya", "soybean"], "soybeans"),
        (["wheat", "gluten", "spelt", "rye", "barley"], "cereals_containing_gluten"),
        (["milk", "whey", "casein", "lactose", "dairy", "butter", "cream"], "milk"),
        (["peanut", "groundnut"], "peanuts"),
        (["sesame"], "sesame"),
        (["lupin", "lupine"], "lupin"),
        (["sulphit", "sulfite", "sulphur"], "sulphur_dioxide_sulphites"),
        (["celery"], "celery"),
        (["mustard"], "mustard"),
        (["egg", "albumin", "lecithin"] if "egg" in name_lower else ["egg"], "eggs"),
    ]
    for keywords, allergen in checks:
        if any(kw in name_lower for kw in keywords):
            found.append(allergen)
    return found


def _labels_to_organic(labels: list[str]) -> Optional[bool]:
    label_str = " ".join(l.lower() for l in labels)
    if "organic" in label_str:
        return True
    if "non organic" in label_str or "conventional" in label_str:
        return False
    return None


def _labels_to_gmo(labels: list[str]) -> Optional[str]:
    label_str = " ".join(l.lower() for l in labels)
    if "no gmo" in label_str or "non gmo" in label_str or "gmo free" in label_str:
        return "non_gmo"
    if "gmo" in label_str:
        return "gmo_possible"
    return None


def _infer_organic(name: str) -> Optional[bool]:
    if "organic" in name.lower():
        return True
    if "non-organic" in name.lower() or "conventional" in name.lower():
        return False
    return None


def _empty_enrichment(ingredient_name: str, note: str = "") -> dict:
    return {
        "ingredient": ingredient_name,
        "e_number": None,
        "allergens_confirmed": [],
        "organic_certified": None,
        "regulatory_references": [],
        "confidence_upgrade": 0.0,
        "source": "not_enriched",
        "note": note,
    }
