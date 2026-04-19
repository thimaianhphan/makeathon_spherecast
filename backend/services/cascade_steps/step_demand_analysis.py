"""Cascade Step 1: Demand Analysis."""

from __future__ import annotations

from backend.services.consolidation_service import compute_demand_matrix


async def run_step_demand_analysis(boms: list[dict], raw_materials: list[dict], emit) -> dict:
    """Aggregate raw material demand across all companies and BOMs."""
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "demand_analysis",
        summary="Analysing ingredient demand across all BOMs...",
    )
    demand_matrix = await compute_demand_matrix(boms, raw_materials)
    cross_company = demand_matrix.get("cross_company_candidates", [])
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "demand_analysis",
        summary=(
            f"Demand analysis complete. {len(boms)} BOMs across "
            f"{demand_matrix['total_raw_materials']} raw materials. "
            f"{len(cross_company)} cross-company consolidation candidates found."
        ),
    )
    return demand_matrix
