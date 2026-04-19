"""Cascade Step 5: Supplier Mapping & Consolidation."""

from __future__ import annotations

from backend.services.consolidation_service import generate_sourcing_proposal


async def run_step_consolidation(demand_matrix: dict, supplier_mappings: list[dict], substitution_graph: dict, emit) -> list:
    """Map substitution candidates to available suppliers and compute consolidation opportunities."""
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "consolidation",
        summary="Computing supplier consolidation opportunities...",
    )
    proposals = await generate_sourcing_proposal(demand_matrix, supplier_mappings, substitution_graph)
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "consolidation",
        summary=(
            f"Consolidation analysis complete. "
            f"{len(proposals)} sourcing group(s) with recommendations generated."
        ),
    )
    return proposals
