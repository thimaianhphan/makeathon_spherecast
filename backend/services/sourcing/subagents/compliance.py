"""
Compliance sub-agent.

Wraps substitution_service.infer_eu_compliance, passing supplier evidence
as enrichment_data so the LLM can cite real ground truth.

Evidence trust hierarchy (per brief):
  1. Regulatory / certification DB confirmations  → source="database"
  2. Supplier official website / spec sheet       → source="enriched"
  3. Reputable news / trade publications          → source="enriched" (lower confidence cap)
  4. LLM inference without external support       → source="inferred", confidence ≤ 0.6
"""

from __future__ import annotations

import json

from backend.schemas import ComplianceResult, SubstitutionCandidate, SupplierEvidence
from backend.services.substitution_service import infer_eu_compliance


async def check_compliance(
    candidate: SubstitutionCandidate,
    original: dict,
    finished_product: dict,
    bom_components: list[dict],
    supplier_evidence: list[SupplierEvidence],
) -> ComplianceResult:
    """
    Run all four EU compliance checks for one candidate.
    Passes supplier evidence as enrichment_data, enabling 'enriched' sourcing.
    """
    enrichment_data = _build_enrichment_dict(supplier_evidence)

    substitute_dict = {
        "Id": candidate.substitute_product_id,
        "Name": candidate.substitute_name,
        "SKU": str(candidate.substitute_product_id),
    }
    original_dict = {
        "Id": original.get("Id", original.get("product_id", 0)),
        "Name": original.get("Name", original.get("name", "")),
        "SKU": original.get("SKU", str(original.get("Id", 0))),
    }

    result = await infer_eu_compliance(
        substitute=substitute_dict,
        original=original_dict,
        finished_product=finished_product,
        existing_bom=bom_components,
        enrichment_data=enrichment_data if enrichment_data else None,
    )

    # Cap inferred-only checks at confidence 0.6 (per brief)
    capped_checks = []
    for check in result.checks:
        if check.source == "inferred" and check.confidence > 0.6:
            check = check.model_copy(update={"confidence": 0.6})
        capped_checks.append(check)

    return result.model_copy(update={"checks": capped_checks})


def _build_enrichment_dict(evidence_list: list[SupplierEvidence]) -> dict | None:
    """
    Flatten SupplierEvidence records into a dict the LLM can reason over.
    Only includes non-empty evidence; returns None if all records are no_evidence.
    """
    enriched = [e for e in evidence_list if e.source_type != "no_evidence"]
    if not enriched:
        return None

    items = []
    for ev in enriched:
        item: dict = {
            "supplier": ev.supplier_name,
            "source_type": ev.source_type,
            "confidence": ev.confidence,
            "source_urls": ev.source_urls,
        }
        if ev.claimed_certifications:
            item["certifications"] = ev.claimed_certifications
        if ev.country_of_origin:
            item["country_of_origin"] = ev.country_of_origin
        if ev.red_flags:
            item["red_flags"] = ev.red_flags
        if ev.unit_price_eur is not None:
            item["unit_price_eur"] = ev.unit_price_eur
        if ev.moq is not None:
            item["moq"] = ev.moq
        if ev.lead_time_days is not None:
            item["lead_time_days"] = ev.lead_time_days
        items.append(item)

    return {"supplier_evidence": items}
