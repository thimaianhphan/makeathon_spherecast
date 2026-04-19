"""
Supplier Scout sub-agent.

For each candidate raw material:
  1. Queries the DB for suppliers that offer it.
  2. Ranks suppliers by scale (total products offered — crude proxy).
  3. Consults the persistent Supplier_Price_Cache (warm_cache) before any HTTP.
  4. Web-searches + fetches the top 2-3 suppliers' pages (only for non-cached, non-opaque).
  5. Uses LLM to extract structured evidence (price, MOQ, certifications, flags).
  6. Upserts result into Supplier_Price_Cache for future runs.
  7. Returns a SupplierEvidence record per (supplier, candidate) pair scouted.

Lookup order per (supplier, candidate):
  1. run_cache  — cheapest, same-process in-memory.
  2. warm_cache — persistent SQLite, pre-fetched as a batch before the loop.
  3. live scrape — HTTP + LLM extraction.

Tier handling:
  - opaque    → short-circuit immediately to no_evidence (no HTTP, no LLM).
  - full / full_3p → site-scoped query e.g. "site:bulksupplements.com {material}".
  - spec_only → generic query + price-free SUPPLIER_SPEC_ONLY_PROMPT.

Rules:
- Never fabricates URLs. Only uses URLs returned by the search API.
- If no search results return, returns a no_evidence record.
- Opaque no_evidence records are NOT written to the persistent cache.
- Caches every non-opaque (supplier_id, candidate_product_id) result within the run.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from backend.schemas import SupplierEvidence
from backend.time_utils import utc_now_iso
from backend.services.sourcing import cache as run_cache
from backend.services.sourcing.prompts import (
    SUPPLIER_EXTRACTION_PROMPT,
    SUPPLIER_SPEC_ONLY_PROMPT,
)

# How many suppliers to scout per candidate
MAX_SUPPLIERS_PER_CANDIDATE = 3
# How many URLs to fetch per supplier search
MAX_URLS_PER_SUPPLIER = 2

# Domains known to be news/cert/aggregator — order matters (first match wins)
_CERT_DOMAINS = {"brcgs.com", "fssc.com", "ifs-certification.com", "msc.org",
                 "rainforest-alliance.org", "sgs.com", "bureauveritas.com", "nsf.org"}
_NEWS_DOMAINS = {"reuters.com", "businesswire.com", "prnewswire.com", "foodnavigator.com",
                 "foodbev.com", "just-food.com", "foodingredientsfirst.com"}
_AGGREGATOR_DOMAINS = {"alibaba.com", "amazon.com", "globalsources.com", "indiamart.com",
                       "thomasnet.com", "kompass.com", "ecplaza.net"}


async def scout_suppliers(
    candidates: list[dict],
    supplier_product_mappings: list[dict],
) -> list[SupplierEvidence]:
    """
    candidates: list of {Id, SKU, Name} dicts for candidate raw materials.
    supplier_product_mappings: full Supplier_Product join from db_service.
    Returns one SupplierEvidence per (supplier, candidate) pair scouted.
    """
    # Pre-compute supplier scale once per run
    _ensure_supplier_scales(supplier_product_mappings)

    # Build supplier lookup: product_id → list[{supplier_id, supplier_name}]
    product_supplier_map: dict[int, list[dict]] = {}
    for row in supplier_product_mappings:
        pid = row["product_id"]
        product_supplier_map.setdefault(pid, []).append({
            "supplier_id": row["supplier_id"],
            "supplier_name": row["supplier_name"],
        })

    # ── Collect all (supplier_id, product_id) pairs for batch warm-cache lookup ──
    all_pairs: list[tuple[int, int]] = []
    ranked_per_candidate: list[tuple[dict, list[dict]]] = []
    for candidate in candidates:
        pid = candidate["Id"]
        suppliers = product_supplier_map.get(pid, [])
        if not suppliers:
            ranked_per_candidate.append((candidate, []))
            continue
        ranked = sorted(
            suppliers,
            key=lambda s: run_cache.get_supplier_scale(s["supplier_id"]),
            reverse=True,
        )[:MAX_SUPPLIERS_PER_CANDIDATE]
        ranked_per_candidate.append((candidate, ranked))
        for sup in ranked:
            all_pairs.append((sup["supplier_id"], pid))

    # Batch-fetch warm (persistent) cache; run_cache-hit pairs will be skipped below
    from backend.services.sourcing import price_cache
    warm_cache: dict[tuple[int, int], SupplierEvidence] = {}
    if all_pairs:
        try:
            warm_cache = price_cache.get_many(all_pairs)
        except Exception:
            warm_cache = {}

    # ── Main per-candidate loop ───────────────────────────────────────────────
    all_evidence: list[SupplierEvidence] = []
    for candidate, ranked in ranked_per_candidate:
        pid = candidate["Id"]

        if not ranked:
            all_evidence.append(_no_evidence(0, "unknown", pid))
            continue

        for sup in ranked:
            supplier_id = sup["supplier_id"]
            supplier_name = sup["supplier_name"]

            # 1. run_cache (cheapest)
            cached = run_cache.get_scout(supplier_id, pid)
            if cached is not None:
                all_evidence.append(cached)
                continue

            # 2. warm_cache (persistent SQLite, pre-fetched)
            warm_hit = warm_cache.get((supplier_id, pid))
            if warm_hit is not None:
                # Mirror into run_cache so sibling pipelines in the same run benefit
                run_cache.put_scout(supplier_id, pid, warm_hit)
                all_evidence.append(warm_hit)
                continue

            # 3. Live scrape
            ev = await _scout_one(supplier_id, supplier_name, candidate)
            run_cache.put_scout(supplier_id, pid, ev)

            # Upsert into persistent cache — but NEVER for opaque/no_evidence
            if ev.source_type != "no_evidence":
                from backend.services.sourcing import supplier_registry
                from backend.services.sourcing.sku_utils import material_name_from_sku
                access = supplier_registry.get_access(supplier_name)
                tier = access["tier"] if access else "opaque"
                if tier != "opaque":
                    raw_sku = candidate.get("SKU") or candidate.get("Name", "")
                    mat = material_name_from_sku(raw_sku)
                    try:
                        price_cache.put(ev, product_id=pid, material_name=mat)
                    except Exception:
                        pass  # non-fatal

            all_evidence.append(ev)

    return all_evidence


async def _scout_one(
    supplier_id: int,
    supplier_name: str,
    candidate: dict,
) -> SupplierEvidence:
    from backend.services.retrieval.web_search import search
    from backend.services.retrieval.web_fetch import fetch_clean
    from backend.services.sourcing import supplier_registry
    from backend.services.sourcing.sku_utils import material_name_from_sku

    # ── Tier resolution ───────────────────────────────────────────────────────
    access = supplier_registry.get_access(supplier_name)
    tier = access["tier"] if access else "opaque"

    # Short-circuit for opaque suppliers — no HTTP, no LLM
    if tier == "opaque":
        return _no_evidence(supplier_id, supplier_name, candidate["Id"])

    raw_sku = candidate.get("SKU") or candidate.get("Name", "")
    material_name = material_name_from_sku(raw_sku)

    # ── Build tier-appropriate search query ───────────────────────────────────
    if access and access.get("search_pattern"):
        query = access["search_pattern"].format(material=material_name)
    else:
        # spec_only suppliers: no site: scope, no price terms
        query = f'"{supplier_name}" "{material_name}" spec sheet OR datasheet'

    price_expected = (tier != "spec_only")
    now = utc_now_iso()

    try:
        hits = await search(query, max_results=5)
    except Exception:
        hits = []

    if not hits:
        ev = _no_evidence(supplier_id, supplier_name, candidate["Id"])
        ev = ev.model_copy(update={"fetched_at": now})
        return ev

    # Prefer supplier's own domain URLs
    supplier_words = {w.lower() for w in supplier_name.split() if len(w) > 3}
    supplier_hits = [h for h in hits if _domain_matches_supplier(h.url, supplier_words)]
    other_hits = [h for h in hits if h not in supplier_hits]
    ordered_hits = (supplier_hits + other_hits)[:MAX_URLS_PER_SUPPLIER]

    extracted_fields: dict = {}
    source_urls: list[str] = []
    source_type = "no_evidence"

    for hit in ordered_hits:
        page = await fetch_clean(hit.url)
        if page.error or not page.content:
            continue
        source_urls.append(hit.url)
        fields = await _extract_from_page(
            supplier_name, material_name, hit.url, page.content,
            price_expected=price_expected,
        )
        # Merge: first non-null value wins per field
        for k, v in fields.items():
            if v and k not in extracted_fields:
                extracted_fields[k] = v
        source_type = _classify_source_type(hit.url, supplier_words)

    if not source_urls:
        return _no_evidence(supplier_id, supplier_name, candidate["Id"])

    confidence = _estimate_confidence(extracted_fields, source_type)

    return SupplierEvidence(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        candidate_product_id=candidate["Id"],
        unit_price_eur=extracted_fields.get("unit_price_eur"),
        currency_original=extracted_fields.get("currency_original"),
        moq=extracted_fields.get("moq"),
        lead_time_days=extracted_fields.get("lead_time_days"),
        claimed_certifications=extracted_fields.get("claimed_certifications") or [],
        country_of_origin=extracted_fields.get("country_of_origin"),
        red_flags=extracted_fields.get("red_flags") or [],
        source_urls=source_urls,
        source_type=source_type,
        confidence=confidence,
        fetched_at=now,
    )


async def _extract_from_page(
    supplier_name: str,
    product_name: str,
    url: str,
    content: str,
    price_expected: bool = True,
) -> dict:
    """
    Extract structured evidence from a page.

    When price_expected=False (tier=="spec_only"), uses SUPPLIER_SPEC_ONLY_PROMPT
    to avoid wasting tokens on price fields the LLM cannot find, and forcibly
    nulls price-related keys in the returned dict even if the LLM hallucinates.
    """
    from backend.services.agent_service import ai_reason
    from backend.services.substitution_service import _parse_json

    template = SUPPLIER_EXTRACTION_PROMPT if price_expected else SUPPLIER_SPEC_ONLY_PROMPT
    prompt = template.format(
        supplier_name=supplier_name,
        product_name=product_name,
        url=url,
        content=content[:3000],
    )
    try:
        raw = await ai_reason("SupplierScout", "supplier_data_extractor", prompt)
        data = _parse_json(raw) or {}
    except Exception:
        data = {}

    result = {
        "unit_price_eur": _safe_float(data.get("unit_price_eur")),
        "currency_original": _safe_str(data.get("currency_original")),
        "moq": _safe_int(data.get("moq")),
        "lead_time_days": _safe_int(data.get("lead_time_days")),
        "claimed_certifications": _safe_list(data.get("claimed_certifications")),
        "country_of_origin": _safe_str(data.get("country_of_origin")),
        "red_flags": _safe_list(data.get("red_flags")),
    }

    # For spec_only: coerce price fields to None even if LLM hallucinated a value
    if not price_expected:
        result["unit_price_eur"] = None
        result["currency_original"] = None
        result["moq"] = None

    return result


def _no_evidence(supplier_id: int, supplier_name: str, product_id: int) -> SupplierEvidence:
    return SupplierEvidence(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        candidate_product_id=product_id,
        source_type="no_evidence",
        confidence=0.0,
        fetched_at=utc_now_iso(),
    )


def _ensure_supplier_scales(mappings: list[dict]) -> None:
    if run_cache.supplier_scales_loaded():
        return
    counts: dict[int, int] = {}
    for row in mappings:
        counts[row["supplier_id"]] = counts.get(row["supplier_id"], 0) + 1
    run_cache.set_supplier_scales(counts)


def _domain_matches_supplier(url: str, supplier_words: set[str]) -> bool:
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return any(word in domain for word in supplier_words)
    except Exception:
        return False


def _classify_source_type(url: str, supplier_words: set[str]) -> str:
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return "aggregator"
    if any(word in domain for word in supplier_words):
        return "supplier_site"
    if domain in _CERT_DOMAINS:
        return "cert_db"
    if domain in _NEWS_DOMAINS:
        return "news"
    return "aggregator"


def _estimate_confidence(fields: dict, source_type: str) -> float:
    base = {"supplier_site": 0.75, "cert_db": 0.85, "news": 0.55, "aggregator": 0.5}.get(
        source_type, 0.4
    )
    filled = sum(1 for v in fields.values() if v)
    bonus = min(filled * 0.03, 0.15)
    return round(min(base + bonus, 1.0), 3)


# ── Type-safe coercers ───────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_str(v) -> str | None:
    return str(v).strip() if v else None


def _safe_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return []
