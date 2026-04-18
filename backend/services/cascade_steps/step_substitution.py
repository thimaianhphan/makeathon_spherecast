"""Cascade Step 2: Substitution Detection."""

from __future__ import annotations

from backend.services.substitution_service import build_substitution_graph


async def run_step_substitution(raw_materials: list[dict], boms: list[dict], emit) -> dict:
    """For each high-demand material group, find functional substitutes."""
    emit(
        "agnes-01", "Agnes",
        "eu-compliance-agent-01", "EU Compliance Validator",
        "substitution_analysis",
        summary="Running LLM-based substitution detection across ingredient categories...",
    )
    graph = await build_substitution_graph(raw_materials, boms)
    viable_count = sum(
        sum(1 for c in g.candidates if c.overall_viable)
        for g in graph.values()
    )
    emit(
        "agnes-01", "Agnes",
        "system", "System",
        "substitution_analysis",
        summary=(
            f"Substitution detection complete. "
            f"{len(graph)} ingredient groups analysed. "
            f"{viable_count} viable substitution candidates identified."
        ),
    )
    return graph
