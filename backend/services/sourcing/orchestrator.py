"""
SourcingOrchestrator — top-level coordinator.

Loads BOM once, fans out one RawMaterialPipeline per component in parallel
(asyncio.gather), collects results into a SourcingProposal.

No reasoning happens here — purely plumbing and aggregation.
No DB writes from pipelines — only reads.
"""

from __future__ import annotations

import asyncio

from backend.schemas import PipelineResult, SourcingProposal
from backend.time_utils import utc_now_iso
from backend.services import db_service
from backend.services.sourcing import cache as run_cache
from backend.services.sourcing.pipeline import run_pipeline


class SourcingOrchestrator:
    """
    Usage:
        proposal = await SourcingOrchestrator().run(finished_good_id=42)
    """

    async def run(self, finished_good_id: int) -> SourcingProposal:
        # Reset per-run caches so parallel pipelines share a clean slate
        run_cache.clear()

        # ── Load shared data (single DB hit per table) ───────────────────────
        bom = db_service.get_bom_for_product(finished_good_id)
        if not bom:
            raise ValueError(f"No BOM found for product_id={finished_good_id}")

        finished_product = bom["produced_product"]
        components = bom["components"]  # list of {product_id, SKU, Name}

        all_raw_materials = db_service.get_raw_materials()
        supplier_product_mappings = db_service.get_supplier_product_mappings()
        cross_company_demand = db_service.get_cross_company_demand()

        # ── Normalise component dicts to match raw-material schema ───────────
        # BOM components have {product_id, SKU, Name}; raw materials use {Id, SKU, Name}
        bom_component_ids = {c["product_id"] for c in components}
        bom_components_for_compliance = [
            {"Id": c["product_id"], "SKU": c["SKU"], "Name": c["Name"]}
            for c in components
        ]
        target_rms = [
            rm for rm in all_raw_materials
            if rm["Id"] in bom_component_ids
        ]

        if not target_rms:
            return SourcingProposal(
                finished_good_id=finished_good_id,
                finished_good_name=finished_product.get("name", finished_product.get("sku", "")),
                finished_good_sku=finished_product.get("sku", ""),
                pipeline_results=[],
                total_estimated_savings_pct=None,
                overall_confidence=0.0,
                generated_at=utc_now_iso(),
            )

        # ── Fan out: one pipeline per raw material, all in parallel ──────────
        tasks = [
            run_pipeline(
                raw_material=rm,
                all_raw_materials=all_raw_materials,
                finished_product=finished_product,
                bom_components=bom_components_for_compliance,
                supplier_product_mappings=supplier_product_mappings,
                cross_company_demand=cross_company_demand,
            )
            for rm in target_rms
        ]
        results: list[PipelineResult] = await asyncio.gather(*tasks)

        # ── Aggregate ────────────────────────────────────────────────────────
        total_savings, overall_conf = _aggregate_metrics(results)

        return SourcingProposal(
            finished_good_id=finished_good_id,
            finished_good_name=finished_product.get("name", finished_product.get("sku", "")),
            finished_good_sku=finished_product.get("sku", ""),
            pipeline_results=list(results),
            total_estimated_savings_pct=total_savings,
            overall_confidence=overall_conf,
            generated_at=utc_now_iso(),
        )


def _aggregate_metrics(
    results: list[PipelineResult],
) -> tuple[float | None, float]:
    """Compute total estimated savings and overall confidence."""
    savings_values = [
        r.estimated_savings_pct
        for r in results
        if r.estimated_savings_pct is not None
    ]
    total_savings = (
        round(sum(savings_values) / len(savings_values), 4)
        if savings_values else None
    )

    # Overall confidence = average of per-pipeline compliance confidence
    confidence_scores: list[float] = []
    for r in results:
        for cand in r.equivalence_candidates:
            if cand.eu_compliance and cand.eu_compliance.checks:
                avg = sum(c.confidence for c in cand.eu_compliance.checks) / len(
                    cand.eu_compliance.checks
                )
                confidence_scores.append(avg)
                break  # only count the best candidate per pipeline

    overall_conf = (
        round(sum(confidence_scores) / len(confidence_scores), 3)
        if confidence_scores else 0.0
    )
    return total_savings, overall_conf
