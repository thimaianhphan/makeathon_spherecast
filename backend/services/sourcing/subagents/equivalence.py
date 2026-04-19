"""
Equivalence sub-agent.

Classifies the original raw material and proposes 3-5 functionally
interchangeable candidates from the full raw-material catalog.

Method: batch LLM classification (file-cached) + rapidfuzz name-similarity
ranking within the same functional category. No web calls, no per-pair LLM.
"""

from __future__ import annotations

from backend.schemas import SubstitutionCandidate, EvidenceItem
from backend.time_utils import utc_now_iso
from backend.services.substitution_service import _classify_all
from backend.services.sourcing import cache as run_cache

MAX_CANDIDATES = 5


async def propose_equivalents(
    original: dict,
    all_raw_materials: list[dict],
) -> list[SubstitutionCandidate]:
    """
    Return up to MAX_CANDIDATES functionally interchangeable SubstitutionCandidates.
    Each candidate has a functional_equivalence_score and an evidence item marked
    source='inferred' (LLM classification + name similarity, no web).
    """
    from backend.services.agent_service import ai_reason

    # Use file-backed + run-cache for classifications
    cached = run_cache.get_all_classifications()
    uncached_rms = [rm for rm in all_raw_materials if rm["Id"] not in cached]

    if uncached_rms:
        new_cls = await _classify_all(uncached_rms, ai_reason)
        run_cache.put_all_classifications(new_cls)
        cached = run_cache.get_all_classifications()

    original_cls = cached.get(original["Id"], {})
    original_category = original_cls.get("category", "other")

    same_category = [
        rm for rm in all_raw_materials
        if rm["Id"] != original["Id"]
        and cached.get(rm["Id"], {}).get("category", "other") == original_category
    ]

    if not same_category:
        return []

    # Rank by name similarity (cheapest signal; no LLM call)
    scored = _rank_by_similarity(original["Name"], same_category)
    top = scored[:MAX_CANDIDATES]

    now = utc_now_iso()
    candidates: list[SubstitutionCandidate] = []
    for rm, sim_score in top:
        evidence = EvidenceItem(
            source_type="llm_inference",
            excerpt="",
            confidence=max(0.4, sim_score),
            timestamp=now,
            claim=(
                f"Functional equivalence by category: "
                f"{original['Name']} → {rm['Name']} [{original_category}]"
            ),
        )
        candidates.append(SubstitutionCandidate(
            original_product_id=original["Id"],
            original_name=original["Name"],
            substitute_product_id=rm["Id"],
            substitute_name=rm["Name"],
            functional_equivalence_score=sim_score,
            eu_compliance=None,
            overall_viable=True,
            confidence=sim_score,
            evidence_trail=[evidence],
            tradeoffs=None,
        ))

    return candidates


def _rank_by_similarity(name: str, candidates: list[dict]) -> list[tuple[dict, float]]:
    try:
        from rapidfuzz import fuzz
        scored = [
            (rm, fuzz.token_set_ratio(name, rm["Name"]) / 100.0)
            for rm in candidates
        ]
    except ImportError:
        # Fallback: uniform mid-score so pipeline continues without rapidfuzz
        scored = [(rm, 0.5) for rm in candidates]
    return sorted(scored, key=lambda x: x[1], reverse=True)
