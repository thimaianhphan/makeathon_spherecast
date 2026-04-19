"""Cascade Step 4: EU Compliance Inference."""

from __future__ import annotations


async def run_step_compliance(substitution_graph: dict, emit) -> dict:
    """
    EU compliance has already been run per-candidate inside build_substitution_graph.
    This step filters out rejected candidates and emits a compliance summary.
    """
    emit(
        "agnes-01", "Agnes",
        "eu-compliance-agent-01", "EU Compliance Validator",
        "compliance_check",
        summary="Reviewing EU food compliance for all substitution candidates...",
    )
    total = 0
    approved = 0
    rejected = 0
    needs_review = 0

    for group in substitution_graph.values():
        filtered: list = []
        for candidate in group.candidates:
            total += 1
            status = candidate.eu_compliance.overall_status if candidate.eu_compliance else "needs_review"
            if status == "approved":
                approved += 1
                filtered.append(candidate)
            elif status == "rejected":
                rejected += 1
                # Rejected candidates are removed from viable set
                candidate.overall_viable = False
                filtered.append(candidate)
            else:
                needs_review += 1
                filtered.append(candidate)
        group.candidates = filtered

    summary = {
        "total_candidates_checked": total,
        "approved": approved,
        "needs_review": needs_review,
        "rejected": rejected,
    }
    emit(
        "eu-compliance-agent-01", "EU Compliance Validator",
        "agnes-01", "Agnes",
        "compliance_result",
        summary=(
            f"Compliance check complete: {approved} approved, "
            f"{needs_review} need review, {rejected} rejected."
        ),
    )
    return summary
