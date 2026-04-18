"""Cascade Step 6: Tradeoff Analysis."""

from __future__ import annotations


async def run_step_tradeoffs(proposals: list, substitution_graph: dict, emit) -> list[dict]:
    """Surface cost, compliance, and risk tradeoffs, plus evidence quality metrics."""
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "tradeoff_analysis",
        summary="Analysing tradeoffs and evidence quality for each sourcing recommendation...",
    )
    tradeoffs: list[dict] = []
    for proposal in proposals:
        group_id = proposal.group_id
        group = substitution_graph.get(group_id)
        viable_candidates = [c for c in (group.candidates if group else []) if c.overall_viable]
        high_confidence = [c for c in viable_candidates if c.confidence >= 0.7]

        # Compute evidence quality metrics across all viable candidates
        all_evidence = [
            e
            for c in viable_candidates
            for e in c.evidence_trail
        ]
        external_types = {
            "external_api", "web_search", "supplier_website",
            "product_listing", "certification_db", "regulatory_reference",
            "label_image", "internal_db",
        }
        external_items = [e for e in all_evidence if e.source_type in external_types]
        evidence_confidence_avg = (
            round(sum(e.confidence for e in all_evidence) / len(all_evidence), 3)
            if all_evidence else 0.0
        )
        external_evidence_ratio = (
            round(len(external_items) / len(all_evidence), 3)
            if all_evidence else 0.0
        )

        tradeoffs.append({
            "group_id": group_id,
            "viable_candidates": len(viable_candidates),
            "high_confidence_substitutions": len(high_confidence),
            "recommended_supplier_count": len(proposal.recommended_suppliers),
            "companies_benefiting": proposal.companies_benefiting,
            "evidence_quality": {
                "total_evidence_items": len(all_evidence),
                "external_evidence_items": len(external_items),
                "evidence_confidence_avg": evidence_confidence_avg,
                "external_evidence_ratio": external_evidence_ratio,
            },
            "tradeoffs": {
                "cost_impact": proposal.estimated_savings_description,
                "compliance_risk": _summarise_compliance_risk(viable_candidates),
                "single_source_risk": any(
                    "single_source_risk" in flag
                    for sup in proposal.recommended_suppliers
                    for flag in sup.risk_flags
                ),
                "lead_time_impact": "Similar lead times expected within same ingredient category.",
            },
        })

    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "tradeoff_analysis",
        summary=f"Tradeoff analysis complete for {len(tradeoffs)} group(s).",
    )
    return tradeoffs


def _summarise_compliance_risk(candidates: list) -> str:
    if not candidates:
        return "No viable candidates; compliance not applicable."
    uncertain = sum(
        1 for c in candidates
        if c.eu_compliance and c.eu_compliance.overall_status == "needs_review"
    )
    if uncertain == 0:
        return "All viable candidates approved under EU food regulations."
    return f"{uncertain}/{len(candidates)} candidates require manual compliance review."
