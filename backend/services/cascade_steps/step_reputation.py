"""Cascade Step 8: Reputation & Trust Scoring."""

from __future__ import annotations

from backend.services.trust_service import reputation_ledger


def run_step_reputation(proposals: list, supplier_mappings: list[dict], emit) -> dict:
    """Score suppliers based on consolidation coverage, compliance, and relationship breadth."""
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "reputation",
        summary="Recording supplier transactions and updating trust scores...",
    )
    # Build supplier coverage scores
    sup_scores: dict[str, dict] = {}
    for proposal in proposals:
        for rec in proposal.recommended_suppliers:
            sid = str(rec.supplier_id)
            if sid not in sup_scores:
                sup_scores[sid] = {
                    "supplier_id": rec.supplier_id,
                    "supplier_name": rec.supplier_name,
                    "groups_covered": 0,
                    "total_materials_covered": 0,
                    "volume_leverage_score": 0.0,
                    "risk_flags": [],
                }
            sup_scores[sid]["groups_covered"] += 1
            sup_scores[sid]["total_materials_covered"] += len(rec.materials_covered)
            sup_scores[sid]["volume_leverage_score"] = max(
                sup_scores[sid]["volume_leverage_score"], rec.volume_leverage_score
            )
            sup_scores[sid]["risk_flags"].extend(rec.risk_flags)

    summary = {
        "suppliers_evaluated": len(sup_scores),
        "top_suppliers": sorted(
            sup_scores.values(),
            key=lambda x: x["volume_leverage_score"],
            reverse=True,
        )[:5],
    }
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "reputation",
        summary=f"Reputation step complete. {len(sup_scores)} supplier(s) evaluated.",
    )
    return summary
