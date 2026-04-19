"""
Smoke test for the Agnes sourcing pipeline.

Picks the first FG-iherb-* finished good from the DB and runs the full
orchestrator end-to-end. Validates structural guarantees, not business outcomes.

Run with:
    pytest backend/tests/test_sourcing_pipeline.py -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from backend.services import db_service
from backend.services.sourcing.orchestrator import SourcingOrchestrator
from backend.schemas import PipelineResult, SourcingProposal


def _pick_target_product() -> dict | None:
    """Return the first FG-iherb-* finished good, or the first finished good if none."""
    fgs = db_service.get_finished_goods()
    iherb = [fg for fg in fgs if fg.get("SKU", "").startswith("FG-iherb-")]
    return iherb[0] if iherb else (fgs[0] if fgs else None)


@pytest.mark.asyncio
async def test_orchestrator_produces_proposal():
    """Running the orchestrator returns a SourcingProposal for a real finished good."""
    product = _pick_target_product()
    if product is None:
        pytest.skip("No finished goods in the database.")

    proposal = await SourcingOrchestrator().run(product["Id"])

    assert isinstance(proposal, SourcingProposal)
    assert proposal.finished_good_id == product["Id"]
    assert proposal.generated_at  # non-empty timestamp


@pytest.mark.asyncio
async def test_every_bom_component_has_pipeline_result():
    """Every raw material in the BOM must have a corresponding PipelineResult."""
    product = _pick_target_product()
    if product is None:
        pytest.skip("No finished goods in the database.")

    bom = db_service.get_bom_for_product(product["Id"])
    assert bom is not None, "BOM not found for target product"
    component_ids = {c["product_id"] for c in bom["components"]}

    proposal = await SourcingOrchestrator().run(product["Id"])
    result_ids = {r.original_raw_material_id for r in proposal.pipeline_results}

    assert component_ids == result_ids, (
        f"Missing pipeline results for components: {component_ids - result_ids}"
    )


@pytest.mark.asyncio
async def test_every_result_has_evidence_or_no_evidence_record():
    """
    Every PipelineResult must have at least one EvidenceItem in its evidence_trail,
    OR at least one SupplierEvidence record (including no_evidence type).
    An empty trail with zero supplier_evidence is a data integrity violation.
    """
    product = _pick_target_product()
    if product is None:
        pytest.skip("No finished goods in the database.")

    proposal = await SourcingOrchestrator().run(product["Id"])

    for result in proposal.pipeline_results:
        has_evidence_trail = len(result.evidence_trail) > 0
        has_supplier_evidence = len(result.supplier_evidence) > 0
        assert has_evidence_trail or has_supplier_evidence, (
            f"PipelineResult for '{result.original_raw_material_name}' "
            f"(id={result.original_raw_material_id}) has neither evidence_trail "
            f"nor supplier_evidence — traceability requirement violated."
        )


@pytest.mark.asyncio
async def test_no_accept_without_non_inferred_evidence():
    """
    A decision of 'accept' must be backed by at least one evidence item whose
    source is NOT 'llm_inference' (i.e. web-fetched or database-sourced).
    """
    product = _pick_target_product()
    if product is None:
        pytest.skip("No finished goods in the database.")

    proposal = await SourcingOrchestrator().run(product["Id"])

    for result in proposal.pipeline_results:
        if result.judge_decision != "accept":
            continue

        has_non_inferred = False

        # Check evidence_trail
        for ev in result.evidence_trail:
            if ev.source_type != "llm_inference":
                has_non_inferred = True
                break

        # Check compliance checks on winning candidate
        if not has_non_inferred:
            for cand in result.equivalence_candidates:
                if cand.substitute_product_id != result.recommended_substitute_id:
                    continue
                if cand.eu_compliance:
                    for check in cand.eu_compliance.checks:
                        if check.source in ("enriched", "database"):
                            has_non_inferred = True
                            break

        # Check supplier_evidence
        if not has_non_inferred:
            for se in result.supplier_evidence:
                if se.source_type != "no_evidence" and se.candidate_product_id == result.recommended_substitute_id:
                    has_non_inferred = True
                    break

        assert has_non_inferred, (
            f"'accept' decision for '{result.original_raw_material_name}' "
            f"has no non-inferred evidence — hallucinated compliance claim risk."
        )


@pytest.mark.asyncio
async def test_judge_decisions_are_valid_literals():
    """All judge decisions must be one of accept / needs_review / reject."""
    product = _pick_target_product()
    if product is None:
        pytest.skip("No finished goods in the database.")

    proposal = await SourcingOrchestrator().run(product["Id"])
    valid = {"accept", "needs_review", "reject"}

    for result in proposal.pipeline_results:
        assert result.judge_decision in valid, (
            f"Invalid judge_decision '{result.judge_decision}' for "
            f"'{result.original_raw_material_name}'"
        )
