"""Cascade Step 3: External Enrichment."""

from __future__ import annotations

from datetime import datetime

from backend.schemas import EvidenceItem
from backend.services.enrichment_service import enrich_ingredient_full
from backend.services import evidence_store


async def run_step_enrichment(substitution_graph: dict, emit) -> dict:
    """Enrich ingredient data with multi-source external evidence."""
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "enrichment",
        summary="Enriching ingredient data from external sources (OpenFoodFacts, web search, regulatory refs)...",
    )
    enriched_count = 0
    evidence_count = 0

    for group in substitution_graph.values():
        for candidate in group.candidates:
            enrichment = await enrich_ingredient_full(candidate.substitute_name)

            if enrichment.evidence:
                # Replace or augment the candidate's evidence trail
                non_llm = [e for e in enrichment.evidence if e.source_type != "llm_inference"]
                if non_llm:
                    candidate.evidence_trail.extend(non_llm)
                    enriched_count += 1
                    evidence_count += len(non_llm)

                    # Upgrade confidence slightly based on external evidence quality
                    if enrichment.confidence_delta > 0:
                        candidate.confidence = min(
                            1.0,
                            candidate.confidence + enrichment.confidence_delta * 0.3,
                        )

                    # Emit a live message per enriched ingredient
                    source_types = {e.source_type for e in non_llm}
                    emit(
                        "agnes-01", "Agnes",
                        "system", "System",
                        "enrichment",
                        summary=(
                            f"Enriched '{candidate.substitute_name}': "
                            f"{len(non_llm)} evidence items "
                            f"({', '.join(sorted(source_types))}). "
                            f"Allergens: {enrichment.allergens_confirmed or 'none'}."
                        ),
                    )

    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "enrichment",
        summary=(
            f"Enrichment complete. {enriched_count} candidates upgraded with "
            f"{evidence_count} external evidence items."
        ),
    )
    return {"enriched_candidates": enriched_count, "total_evidence_items": evidence_count}
