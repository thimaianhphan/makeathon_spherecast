"""
RawMaterialPipeline — runs four sub-agents sequentially for one raw material.

Order: Equivalence → Supplier Scout → Compliance → Tradeoff → Judge.
Each stage depends on the previous. Graceful degradation: if any stage
returns empty/error, the pipeline continues and the judge will mark needs_review.
"""

from __future__ import annotations

from backend.schemas import (
    EvidenceItem,
    PipelineResult,
    SubstitutionCandidate,
    SupplierEvidence,
)
from backend.time_utils import utc_now_iso
from backend.services.sourcing.subagents import equivalence as eq_agent
from backend.services.sourcing.subagents import supplier_scout as scout_agent
from backend.services.sourcing.subagents import compliance as comp_agent
from backend.services.sourcing.subagents import tradeoff as tf_agent
from backend.services.sourcing import judge as judge_gate


async def run_pipeline(
    raw_material: dict,
    all_raw_materials: list[dict],
    finished_product: dict,
    bom_components: list[dict],
    supplier_product_mappings: list[dict],
    cross_company_demand: list[dict],
) -> PipelineResult:
    """
    Run the full 4-sub-agent + judge pipeline for one raw material.
    Never raises — all exceptions are caught and surfaced as needs_review results.
    """
    rm_id = raw_material["Id"]
    rm_name = raw_material.get("Name", raw_material.get("SKU", str(rm_id)))

    try:
        return await _run(
            raw_material=raw_material,
            rm_id=rm_id,
            rm_name=rm_name,
            all_raw_materials=all_raw_materials,
            finished_product=finished_product,
            bom_components=bom_components,
            supplier_product_mappings=supplier_product_mappings,
            cross_company_demand=cross_company_demand,
        )
    except Exception as exc:
        # Never let a single pipeline crash the orchestrator
        return _error_result(rm_id, rm_name, str(exc))


async def _run(
    raw_material: dict,
    rm_id: int,
    rm_name: str,
    all_raw_materials: list[dict],
    finished_product: dict,
    bom_components: list[dict],
    supplier_product_mappings: list[dict],
    cross_company_demand: list[dict],
) -> PipelineResult:
    now = utc_now_iso()

    # ── Stage 1: Equivalence ────────────────────────────────────────────────
    eq_candidates: list[SubstitutionCandidate] = []
    try:
        eq_candidates = await eq_agent.propose_equivalents(raw_material, all_raw_materials)
    except Exception:
        pass

    if not eq_candidates:
        return PipelineResult(
            original_raw_material_id=rm_id,
            original_raw_material_name=rm_name,
            judge_decision="reject",
            judge_reasoning="No functionally equivalent candidates found in the raw-material catalog.",
            evidence_trail=[_no_candidate_evidence(rm_name, now)],
            flags_for_human=["No same-category raw materials exist in the catalog for substitution."],
        )

    # ── Stage 2: Supplier Scout ─────────────────────────────────────────────
    candidate_dicts = [
        {"Id": c.substitute_product_id, "SKU": str(c.substitute_product_id), "Name": c.substitute_name}
        for c in eq_candidates
    ]
    supplier_evidence: list[SupplierEvidence] = []
    try:
        supplier_evidence = await scout_agent.scout_suppliers(
            candidates=candidate_dicts,
            supplier_product_mappings=supplier_product_mappings,
        )
    except Exception:
        pass

    # ── Stage 3: Compliance (per candidate) ────────────────────────────────
    compliant_candidates: list[SubstitutionCandidate] = []
    evidence_trail: list[EvidenceItem] = []

    for cand in eq_candidates:
        cand_evidence = [
            e for e in supplier_evidence
            if e.candidate_product_id == cand.substitute_product_id
        ]
        try:
            compliance_result = await comp_agent.check_compliance(
                candidate=cand,
                original=raw_material,
                finished_product=finished_product,
                bom_components=bom_components,
                supplier_evidence=cand_evidence,
            )
        except Exception:
            from backend.services.substitution_service import _default_compliance_checks
            from backend.schemas import ComplianceResult
            compliance_result = ComplianceResult(
                checks=_default_compliance_checks(),
                overall_status="needs_review",
                blocking_issues=["Compliance check failed to execute."],
            )

        updated_cand = cand.model_copy(update={
            "eu_compliance": compliance_result,
            "overall_viable": compliance_result.overall_status != "rejected",
        })
        compliant_candidates.append(updated_cand)

        # Collect compliance evidence items
        if cand_evidence:
            for ev in cand_evidence:
                if ev.source_urls:
                    evidence_trail.append(EvidenceItem(
                        source_type="supplier_website",
                        source_url=ev.source_urls[0],
                        excerpt=f"Supplier data for {ev.supplier_name} / {cand.substitute_name}",
                        confidence=ev.confidence,
                        timestamp=now,
                        claim=f"Supplier evidence: {ev.supplier_name} offers {cand.substitute_name}",
                    ))

    # ── Stage 4: Tradeoff scoring ───────────────────────────────────────────
    scored = tf_agent.rank_candidates(
        candidates=compliant_candidates,
        supplier_evidence=supplier_evidence,
        cross_company_demand=cross_company_demand,
        original_product_id=rm_id,
    )

    # ── Stage 5: Judge ──────────────────────────────────────────────────────
    decision, reasoning, flags = await judge_gate.adjudicate(scored, rm_name)

    # If no evidence trail, ensure at least a no_evidence record exists
    if not evidence_trail and not supplier_evidence:
        evidence_trail.append(_no_evidence_item(rm_name, now))
    elif not evidence_trail:
        all_no_ev = all(e.source_type == "no_evidence" for e in supplier_evidence)
        if all_no_ev:
            evidence_trail.append(_no_evidence_item(rm_name, now))

    # Build final result
    best = scored[0] if scored else None
    return PipelineResult(
        original_raw_material_id=rm_id,
        original_raw_material_name=rm_name,
        equivalence_candidates=compliant_candidates,
        supplier_evidence=supplier_evidence,
        judge_decision=decision,
        judge_reasoning=reasoning,
        recommended_substitute_id=(
            best.candidate.substitute_product_id if best else None
        ),
        recommended_supplier_id=(
            best.recommended_supplier_id if best else None
        ),
        estimated_savings_pct=(
            best.estimated_savings_pct if best else None
        ),
        evidence_trail=evidence_trail,
        flags_for_human=flags,
    )


def _error_result(rm_id: int, rm_name: str, error: str) -> PipelineResult:
    now = utc_now_iso()
    return PipelineResult(
        original_raw_material_id=rm_id,
        original_raw_material_name=rm_name,
        judge_decision="needs_review",
        judge_reasoning=f"Pipeline execution error: {error[:200]}",
        evidence_trail=[EvidenceItem(
            source_type="llm_inference",
            excerpt=f"Pipeline error for {rm_name}: {error[:200]}",
            confidence=0.0,
            timestamp=now,
            claim="Pipeline execution error",
        )],
        flags_for_human=[f"Pipeline error — manual review required: {error[:200]}"],
    )


def _no_candidate_evidence(rm_name: str, now: str) -> EvidenceItem:
    return EvidenceItem(
        source_type="internal_db",
        excerpt=f"No same-category raw materials found in catalog for '{rm_name}'.",
        confidence=1.0,
        timestamp=now,
        claim=f"No substitution candidates for {rm_name}",
    )


def _no_evidence_item(rm_name: str, now: str) -> EvidenceItem:
    return EvidenceItem(
        source_type="llm_inference",
        excerpt=f"No external supplier evidence retrieved for raw material '{rm_name}' candidates.",
        confidence=0.0,
        timestamp=now,
        claim=f"no_evidence: supplier scout returned no results for {rm_name}",
    )
