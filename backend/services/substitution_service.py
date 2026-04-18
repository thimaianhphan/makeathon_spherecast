"""
Substitution Detection Service — Agnes AI Supply Chain Manager.

Determines which raw materials are functionally interchangeable using:
  1. Category-first clustering via single batched LLM call (not O(n²))
  2. rapidfuzz name-similarity for near-duplicate detection
  3. Pairwise LLM evaluation capped at top-20 candidates per material
  4. EU compliance check per candidate

Evidence trail includes supporting EvidenceItems for every check.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from backend.config import EU_14_ALLERGENS, MIN_COMPLIANCE_CONFIDENCE, BLOCK_ON_UNCERTAIN_ALLERGEN
from backend.schemas import (
    ComplianceCheck,
    ComplianceResult,
    EvidenceItem,
    SubstitutionCandidate,
    SubstitutionGroup,
    TradeoffSummary,
)
from backend.time_utils import utc_now_iso

EU_14_ALLERGENS_SET = set(EU_14_ALLERGENS)

# Cached classifications persisted across runs
_CLASSIFICATION_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "rm_classification.json"
)

# Limits to keep LLM cost bounded
MAX_CANDIDATES_PER_MATERIAL = 20
MAX_LLM_PAIRS_PER_CATEGORY = 50  # total pair evaluations per category


COMPLIANCE_PROMPT_TEMPLATE = """You are an EU food regulatory expert. Given:
- Original ingredient: {original_name}
- Proposed substitute: {substitute_name}
- Finished product: {finished_product_name}
- Other ingredients in the BOM: {bom_component_names}
- External evidence (if any): {enrichment_data}

For each check below, determine status (pass/fail/uncertain), confidence (0-1), and reasoning.
Cite which evidence item (by source_type) supports each conclusion.
If no evidence supports a check, status MUST be 'uncertain'.

1. ALLERGEN SAFETY (EU 1169/2011): Does the substitute introduce any of the 14 EU allergens not already present?
2. ADDITIVE APPROVAL (EU 1333/2008): Is the substitute approved for the food category?
3. ORGANIC CONSISTENCY (EU 2018/848): If organic product, is substitute compatible?
4. GMO CONSISTENCY (EU 1829/2003): If non-GMO product, is substitute compatible?

Respond ONLY with valid JSON:
{{
  "checks": [
    {{"check": "allergen_safety", "status": "pass|fail|uncertain", "confidence": 0.0, "reasoning": "...", "source": "inferred|enriched|database", "regulation": "EU 1169/2011"}},
    {{"check": "additive_approval", "status": "pass|fail|uncertain", "confidence": 0.0, "reasoning": "...", "source": "inferred|enriched|database", "regulation": "EU 1333/2008"}},
    {{"check": "organic_consistency", "status": "pass|fail|uncertain", "confidence": 0.0, "reasoning": "...", "source": "inferred|enriched|database", "regulation": "EU 2018/848"}},
    {{"check": "gmo_consistency", "status": "pass|fail|uncertain", "confidence": 0.0, "reasoning": "...", "source": "inferred|enriched|database", "regulation": "EU 1829/2003"}}
  ]
}}"""

BATCH_CLASSIFICATION_PROMPT_TEMPLATE = """Classify the following raw materials for a CPG supply chain.
For each, assign:
1. Functional category (ONE of): emulsifiers, sweeteners, fats_oils, flavourings, preservatives, antioxidants, proteins, starches, acids, vitamins_minerals, colourants, leavening, other
2. EU allergen profile (subset of the 14 EU allergens)
3. Typical food categories under EU Regulation 1333/2008
4. E-number if applicable (else null)

Materials (JSON array):
{materials_json}

Respond ONLY with a JSON object mapping each Id to its classification:
{{
  "<id>": {{"category": "...", "allergens": [], "food_categories": [], "e_number": "E... or null"}},
  ...
}}"""

SUBSTITUTION_PROMPT_TEMPLATE = """Can '{material_a}' (SKU: {sku_a}) be substituted by '{material_b}' (SKU: {sku_b}) in the production of '{finished_good}'?

Consider:
- Functional role in the recipe
- Sensory impact (taste, texture, appearance)
- Processing behaviour (heat stability, solubility, pH sensitivity)
- Regulatory status under EU food law

Rate confidence 0-1 and explain in 2-3 sentences.

Respond ONLY with valid JSON:
{{"viable": true/false, "confidence": 0.0, "reasoning": "...", "key_constraints": ["..."]}}"""


async def build_substitution_graph(
    raw_materials: list[dict],
    boms: list[dict],
) -> dict[str, SubstitutionGroup]:
    """
    Build a substitution graph using category-first clustering and bounded LLM calls.
    Returns {product_id_str: SubstitutionGroup}.
    """
    from backend.services.agent_service import ai_reason

    # Step 1: classify all raw materials (batched + cached)
    classifications = await _classify_all(raw_materials, ai_reason)

    # Step 2: group by category
    category_groups: dict[str, list[dict]] = {}
    for rm in raw_materials:
        cat = classifications.get(rm["Id"], {}).get("category", "other")
        category_groups.setdefault(cat, []).append(rm)

    # Step 3: within each category, find substitution pairs
    graph: dict[str, SubstitutionGroup] = {}
    bom_map = _build_bom_map(boms)

    for category, members in category_groups.items():
        if len(members) < 2:
            continue

        # Detect near-duplicates via rapidfuzz (cheap, no LLM)
        similarity_matrix = _compute_similarity_matrix(members)

        pair_count = 0
        for i, rm_a in enumerate(members):
            group_id = f"{category}-{rm_a['Id']}"
            group = SubstitutionGroup(
                group_id=group_id,
                canonical_material=rm_a,
                members=[m["Id"] for m in members],
                functional_category=category,
                candidates=[],
            )

            # Sort partners by name-similarity (highest first)
            partners = [
                (members[j], similarity_matrix[i][j])
                for j in range(len(members))
                if j != i
            ]
            partners.sort(key=lambda x: x[1], reverse=True)
            partners = partners[:MAX_CANDIDATES_PER_MATERIAL]

            finished_good = _find_finished_good_for_material(rm_a["Id"], boms)
            if not finished_good:
                graph[str(rm_a["Id"])] = group
                continue

            bom_components = bom_map.get(finished_good.get("bom_id", 0), [])

            for rm_b, sim_score in partners:
                if pair_count >= MAX_LLM_PAIRS_PER_CATEGORY:
                    break

                # Near-duplicates (score ≥ 85) can skip LLM and get high-confidence by default
                if sim_score >= 85:
                    candidate = _make_near_duplicate_candidate(rm_a, rm_b, category, sim_score)
                else:
                    prompt = SUBSTITUTION_PROMPT_TEMPLATE.format(
                        material_a=rm_a["Name"],
                        sku_a=rm_a["SKU"],
                        material_b=rm_b["Name"],
                        sku_b=rm_b["SKU"],
                        finished_good=finished_good.get("produced_product", {}).get("name", "CPG product"),
                    )
                    try:
                        raw = await ai_reason("Agnes", "procurement_agent", prompt)
                        sub_data = _parse_json(raw)
                        if not sub_data:
                            continue
                        pair_count += 1
                    except Exception:
                        continue

                    viable = sub_data.get("viable", False)
                    confidence = float(sub_data.get("confidence", 0.0))
                    reasoning = sub_data.get("reasoning", "")

                    evidence = EvidenceItem(
                        source_type="llm_inference",
                        excerpt=reasoning,
                        confidence=confidence,
                        timestamp=utc_now_iso(),
                        claim=f"Functional equivalence of {rm_a['Name']} → {rm_b['Name']}",
                    )

                    compliance = await infer_eu_compliance(
                        substitute=rm_b,
                        original=rm_a,
                        finished_product=finished_good.get("produced_product", {}),
                        existing_bom=bom_components,
                        enrichment_data=None,
                    )

                    overall_viable = viable and compliance.overall_status != "rejected"
                    candidate = SubstitutionCandidate(
                        original_product_id=rm_a["Id"],
                        original_name=rm_a["Name"],
                        substitute_product_id=rm_b["Id"],
                        substitute_name=rm_b["Name"],
                        functional_equivalence_score=confidence,
                        eu_compliance=compliance,
                        overall_viable=overall_viable,
                        confidence=confidence,
                        evidence_trail=[evidence],
                        tradeoffs=TradeoffSummary(
                            cost_impact="To be determined after supplier quote",
                            supplier_consolidation_benefit=f"Potential consolidation within {category} category",
                            lead_time_impact="Similar lead times expected within same category",
                            compliance_risk=compliance.overall_status,
                            risk_notes="; ".join(compliance.blocking_issues) if compliance.blocking_issues else "None identified",
                        ),
                    )

                group.candidates.append(candidate)

            graph[str(rm_a["Id"])] = group

    return graph


async def evaluate_substitute(
    original: dict,
    candidate: dict,
    finished_product: dict,
    bom_components: list[dict],
) -> SubstitutionCandidate:
    """Deep evaluation of a single substitution candidate."""
    from backend.services.agent_service import ai_reason

    prompt = SUBSTITUTION_PROMPT_TEMPLATE.format(
        material_a=original["Name"],
        sku_a=original["SKU"],
        material_b=candidate["Name"],
        sku_b=candidate["SKU"],
        finished_good=finished_product.get("name", "CPG product"),
    )
    try:
        raw = await ai_reason("Agnes", "procurement_agent", prompt)
        sub_data = _parse_json(raw) or {}
    except Exception:
        sub_data = {}

    viable = sub_data.get("viable", False)
    confidence = float(sub_data.get("confidence", 0.0))
    reasoning = sub_data.get("reasoning", "LLM inference unavailable")

    compliance = await infer_eu_compliance(
        substitute=candidate,
        original=original,
        finished_product=finished_product,
        existing_bom=bom_components,
    )

    evidence = EvidenceItem(
        source_type="llm_inference",
        excerpt=reasoning,
        confidence=confidence,
        timestamp=utc_now_iso(),
        claim=f"Functional equivalence evaluation: {original['Name']} → {candidate['Name']}",
    )

    return SubstitutionCandidate(
        original_product_id=original["Id"],
        original_name=original["Name"],
        substitute_product_id=candidate["Id"],
        substitute_name=candidate["Name"],
        functional_equivalence_score=confidence,
        eu_compliance=compliance,
        overall_viable=viable and compliance.overall_status != "rejected",
        confidence=confidence,
        evidence_trail=[evidence],
        tradeoffs=TradeoffSummary(
            cost_impact="To be determined",
            supplier_consolidation_benefit="Consolidation benefit depends on supplier overlap",
            lead_time_impact="Similar expected",
            compliance_risk=compliance.overall_status,
            risk_notes="; ".join(compliance.blocking_issues) if compliance.blocking_issues else "",
        ),
    )


async def infer_eu_compliance(
    substitute: dict,
    original: dict,
    finished_product: dict,
    existing_bom: list[dict],
    enrichment_data: dict | None = None,
) -> ComplianceResult:
    """
    Run all EU compliance checks for a substitution candidate.
    Uses LLM + evidence context; attaches regulatory EvidenceItems.
    """
    from backend.services.agent_service import ai_reason
    from backend.services.retrieval import regulatory
    from backend.services import evidence_store

    bom_names = ", ".join(c.get("Name", c.get("name", "")) for c in existing_bom)

    # Include regulatory context in the prompt
    reg_summaries = []
    for reg_id in ["EU 1169/2011", "EU 1333/2008", "EU 2018/848", "EU 1829/2003"]:
        reg = regulatory.EU_REGULATIONS.get(reg_id)
        if reg:
            reg_summaries.append(f"{reg_id}: {reg.summary}")

    enrichment_str = json.dumps(enrichment_data) if enrichment_data else "None"
    if reg_summaries:
        enrichment_str += "\n\nRegulatory context:\n" + "\n".join(reg_summaries)

    prompt = COMPLIANCE_PROMPT_TEMPLATE.format(
        original_name=original.get("Name", original.get("name", "")),
        substitute_name=substitute.get("Name", substitute.get("name", "")),
        finished_product_name=finished_product.get("name", "CPG product"),
        bom_component_names=bom_names or "Not specified",
        enrichment_data=enrichment_str,
    )

    try:
        raw = await ai_reason("EU Compliance Validator", "compliance_agent", prompt)
        data = _parse_json(raw) or {}
        raw_checks = data.get("checks", [])
    except Exception:
        raw_checks = []

    checks: list[ComplianceCheck] = []
    for ch in raw_checks:
        checks.append(ComplianceCheck(
            check=ch.get("check", "unknown"),
            status=ch.get("status", "uncertain"),
            confidence=float(ch.get("confidence", 0.5)),
            reasoning=ch.get("reasoning", ""),
            source=ch.get("source", "inferred"),
            regulation=ch.get("regulation", ""),
        ))

    if not checks:
        checks = _default_compliance_checks()

    # Attach regulatory reference evidence items for each check
    now = utc_now_iso()
    compliance_evidence: list[EvidenceItem] = []
    for check in checks:
        reg_id = check.regulation
        if reg_id:
            ev = regulatory.get_regulation_evidence(
                reg_id,
                claim=f"{check.check} basis for {substitute.get('Name', '')} substitution",
            )
            if ev:
                compliance_evidence.append(ev)
                evidence_store.record(ev)

    # Determine overall status
    blocking_issues: list[str] = []
    has_fail = False
    has_uncertain_allergen = False

    for check in checks:
        if check.status == "fail":
            has_fail = True
            blocking_issues.append(f"{check.check}: {check.reasoning[:100]}")
        elif check.status == "uncertain" and check.check == "allergen_safety":
            has_uncertain_allergen = True
            if BLOCK_ON_UNCERTAIN_ALLERGEN:
                blocking_issues.append(f"Allergen status uncertain: {check.reasoning[:100]}")

    if has_fail or (BLOCK_ON_UNCERTAIN_ALLERGEN and has_uncertain_allergen):
        overall_status = "rejected"
    elif any(c.status == "uncertain" for c in checks):
        overall_status = "needs_review"
    else:
        overall_status = "approved"

    return ComplianceResult(
        checks=checks,
        overall_status=overall_status,
        blocking_issues=blocking_issues,
    )


# ── Classification helpers ────────────────────────────────────────────────────

async def _classify_all(
    raw_materials: list[dict],
    ai_reason,
) -> dict[int, dict]:
    """Classify all raw materials using cached results + batched LLM call for unknowns."""
    classifications = _load_classification_cache()

    uncached = [rm for rm in raw_materials if rm["Id"] not in classifications]
    if uncached:
        new_classifications = await _batch_classify(uncached, ai_reason)
        classifications.update(new_classifications)
        _save_classification_cache(classifications)

    return classifications


async def _batch_classify(materials: list[dict], ai_reason) -> dict[int, dict]:
    """Batched LLM classification with inter-batch delay to avoid 429s."""
    import asyncio
    batch_size = 30
    result: dict[int, dict] = {}

    for batch_idx, i in enumerate(range(0, len(materials), batch_size)):
        if batch_idx > 0:
            await asyncio.sleep(2)  # 2-second gap between batches to stay under RPM limit
        batch = materials[i: i + batch_size]
        items = [{"Id": m["Id"], "Name": m["Name"], "SKU": m["SKU"]} for m in batch]
        prompt = BATCH_CLASSIFICATION_PROMPT_TEMPLATE.format(
            materials_json=json.dumps(items, ensure_ascii=False)
        )
        try:
            raw = await ai_reason("Agnes", "procurement_agent", prompt)
            data = _parse_json(raw) or {}
            for rm in batch:
                key = str(rm["Id"])
                if key in data:
                    result[rm["Id"]] = data[key]
                else:
                    result[rm["Id"]] = {"category": "other", "allergens": [], "food_categories": [], "e_number": None}
        except Exception:
            for rm in batch:
                result[rm["Id"]] = {"category": "other", "allergens": [], "food_categories": [], "e_number": None}

    return result


def _compute_similarity_matrix(members: list[dict]) -> list[list[float]]:
    """Compute token_set_ratio similarity matrix for all member names."""
    try:
        from rapidfuzz import fuzz
        n = len(members)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = fuzz.token_set_ratio(
                        members[i]["Name"], members[j]["Name"]
                    )
        return matrix
    except ImportError:
        # Fallback: uniform 0 (no rapidfuzz available)
        n = len(members)
        return [[0.0] * n for _ in range(n)]


def _make_near_duplicate_candidate(
    rm_a: dict, rm_b: dict, category: str, sim_score: float
) -> SubstitutionCandidate:
    """High-confidence candidate for near-duplicate names (no LLM needed)."""
    compliance = ComplianceResult(
        checks=_default_compliance_checks(),
        overall_status="needs_review",
        blocking_issues=[],
    )
    evidence = EvidenceItem(
        source_type="llm_inference",
        excerpt=(
            f"Near-duplicate name match: '{rm_a['Name']}' ↔ '{rm_b['Name']}' "
            f"(similarity score: {sim_score:.0f}/100). Likely same ingredient with variant naming."
        ),
        confidence=sim_score / 100.0,
        timestamp=utc_now_iso(),
        claim=f"Name-similarity evidence: {rm_a['Name']} ≈ {rm_b['Name']}",
    )
    return SubstitutionCandidate(
        original_product_id=rm_a["Id"],
        original_name=rm_a["Name"],
        substitute_product_id=rm_b["Id"],
        substitute_name=rm_b["Name"],
        functional_equivalence_score=sim_score / 100.0,
        eu_compliance=compliance,
        overall_viable=True,
        confidence=sim_score / 100.0,
        evidence_trail=[evidence],
        tradeoffs=TradeoffSummary(
            cost_impact="Likely identical cost — same ingredient",
            supplier_consolidation_benefit=f"Direct consolidation within {category} category",
            lead_time_impact="Identical",
            compliance_risk="needs_review",
            risk_notes="Name variants detected; verify they are truly the same ingredient",
        ),
    )


def _load_classification_cache() -> dict[int, dict]:
    try:
        if os.path.exists(_CLASSIFICATION_CACHE_PATH):
            with open(_CLASSIFICATION_CACHE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return {int(k): v for k, v in raw.items()}
    except Exception:
        pass
    return {}


def _save_classification_cache(data: dict[int, dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_CLASSIFICATION_CACHE_PATH), exist_ok=True)
        with open(_CLASSIFICATION_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in data.items()}, f, indent=2)
    except Exception:
        pass


def _default_compliance_checks() -> list[ComplianceCheck]:
    return [
        ComplianceCheck(
            check="allergen_safety",
            status="uncertain",
            confidence=0.4,
            reasoning="LLM inference unavailable; allergen status could not be determined.",
            source="inferred",
            regulation="EU 1169/2011",
        ),
        ComplianceCheck(
            check="additive_approval",
            status="uncertain",
            confidence=0.4,
            reasoning="LLM inference unavailable; additive approval could not be verified.",
            source="inferred",
            regulation="EU 1333/2008",
        ),
        ComplianceCheck(
            check="organic_consistency",
            status="uncertain",
            confidence=0.5,
            reasoning="Organic status unknown.",
            source="inferred",
            regulation="EU 2018/848",
        ),
        ComplianceCheck(
            check="gmo_consistency",
            status="uncertain",
            confidence=0.5,
            reasoning="GMO status unknown.",
            source="inferred",
            regulation="EU 1829/2003",
        ),
    ]


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    try:
        return json.loads(text)
    except Exception:
        return None


def _build_bom_map(boms: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for bom in boms:
        result[bom["bom_id"]] = bom.get("components", [])
    return result


def _find_finished_good_for_material(product_id: int, boms: list[dict]) -> dict | None:
    for bom in boms:
        for comp in bom.get("components", []):
            if comp.get("product_id") == product_id:
                return bom
    return None
