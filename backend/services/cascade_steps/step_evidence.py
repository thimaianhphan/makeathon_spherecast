"""Cascade Step 7: Evidence Trail Compilation."""

from __future__ import annotations


def compile_evidence_trails(substitution_graph: dict, proposals: list, tradeoffs: list[dict]) -> list[dict]:
    """Compile all reasoning chains, sources, and confidence scores into a structured evidence trail."""
    trails: list[dict] = []
    for proposal in proposals:
        group = substitution_graph.get(proposal.group_id)
        if not group:
            continue
        trail_items: list[dict] = []
        for candidate in group.candidates:
            if not candidate.overall_viable:
                continue
            for ev in candidate.evidence_trail:
                trail_items.append({
                    "original": candidate.original_name,
                    "substitute": candidate.substitute_name,
                    "source_type": ev.source_type,
                    "source_url": ev.source_url,
                    "excerpt": ev.excerpt,
                    "confidence": ev.confidence,
                    "timestamp": ev.timestamp,
                })
            if candidate.eu_compliance:
                for check in candidate.eu_compliance.checks:
                    trail_items.append({
                        "original": candidate.original_name,
                        "substitute": candidate.substitute_name,
                        "source_type": "compliance_check",
                        "check": check.check,
                        "status": check.status,
                        "confidence": check.confidence,
                        "regulation": check.regulation,
                        "reasoning": check.reasoning,
                    })
        trails.append({
            "group_id": proposal.group_id,
            "functional_category": group.functional_category,
            "companies_benefiting": proposal.companies_benefiting,
            "evidence_items": trail_items,
        })
    return trails
