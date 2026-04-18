"""
Consolidation & Optimization Service — Agnes AI Supply Chain Manager.

Aggregates ingredient demand across companies and BOMs,
then generates consolidated sourcing proposals.
"""

from __future__ import annotations

from backend.schemas import (
    ConsolidationProposal,
    SubstitutionGroup,
    SupplierRecommendation,
)


async def compute_demand_matrix(
    boms: list[dict],
    raw_materials: list[dict],
) -> dict:
    """
    Build a matrix: for each raw material (and its substitution group),
    aggregate total demand across all companies and BOMs.
    """
    raw_material_map = {rm["Id"]: rm for rm in raw_materials}
    demand: dict[int, dict] = {}

    for bom in boms:
        produced = bom.get("produced_product", {})
        company_id = produced.get("company_id")
        company_name = produced.get("company_name", "Unknown")
        bom_id = bom.get("bom_id")

        for comp in bom.get("components", []):
            pid = comp.get("product_id")
            if pid not in demand:
                rm = raw_material_map.get(pid, {})
                demand[pid] = {
                    "product_id": pid,
                    "product_name": rm.get("Name", comp.get("Name", "Unknown")),
                    "product_sku": rm.get("SKU", ""),
                    "bom_count": 0,
                    "consuming_companies": [],
                    "consuming_bom_ids": [],
                }
            demand[pid]["bom_count"] += 1
            demand[pid]["consuming_bom_ids"].append(bom_id)
            entry = {"company_id": company_id, "company_name": company_name, "bom_id": bom_id}
            if entry not in demand[pid]["consuming_companies"]:
                demand[pid]["consuming_companies"].append(entry)

    return {
        "ingredients": list(demand.values()),
        "total_boms": len(boms),
        "total_raw_materials": len(raw_materials),
        "cross_company_candidates": [
            v for v in demand.values()
            if len({e["company_id"] for e in v["consuming_companies"]}) > 1
        ],
    }


async def generate_sourcing_proposal(
    demand_matrix: dict,
    supplier_mappings: list[dict],
    substitution_graph: dict,
) -> list[ConsolidationProposal]:
    """
    For each substitution group, identify suppliers that can serve consolidated demand,
    and produce a ranked list of sourcing recommendations.
    """
    # Build supplier → product coverage map
    supplier_coverage: dict[int, dict] = {}
    for mapping in supplier_mappings:
        sid = mapping["supplier_id"]
        if sid not in supplier_coverage:
            supplier_coverage[sid] = {
                "supplier_id": sid,
                "supplier_name": mapping["supplier_name"],
                "product_ids": [],
            }
        supplier_coverage[sid]["product_ids"].append(mapping["product_id"])

    proposals: list[ConsolidationProposal] = []

    for group_id, group_raw in substitution_graph.items():
        if isinstance(group_raw, SubstitutionGroup):
            group = group_raw
        else:
            continue

        member_ids = group.members
        if not member_ids:
            continue

        # Find suppliers that cover ≥1 member of this group
        relevant_suppliers = []
        for sid, cov in supplier_coverage.items():
            covered = [pid for pid in member_ids if pid in cov["product_ids"]]
            if covered:
                relevant_suppliers.append({
                    "supplier_id": sid,
                    "supplier_name": cov["supplier_name"],
                    "materials_covered": covered,
                    "coverage_count": len(covered),
                })

        if not relevant_suppliers:
            continue

        # Rank by coverage count
        relevant_suppliers.sort(key=lambda x: x["coverage_count"], reverse=True)

        recommendations = []
        for sup in relevant_suppliers[:3]:  # top 3
            coverage_pct = sup["coverage_count"] / max(len(member_ids), 1)
            recommendations.append(SupplierRecommendation(
                supplier_id=sup["supplier_id"],
                supplier_name=sup["supplier_name"],
                materials_covered=sup["materials_covered"],
                volume_leverage_score=round(coverage_pct, 2),
                consolidation_benefit=_describe_benefit(sup["coverage_count"], len(member_ids)),
                risk_flags=_assess_risks(coverage_pct, sup["coverage_count"]),
            ))

        # Determine benefiting companies from demand matrix
        benefiting_companies: list[str] = []
        for ing in demand_matrix.get("ingredients", []):
            if ing["product_id"] in member_ids:
                for ce in ing["consuming_companies"]:
                    cn = ce.get("company_name", "")
                    if cn and cn not in benefiting_companies:
                        benefiting_companies.append(cn)

        total_bom_coverage = sum(
            ing["bom_count"]
            for ing in demand_matrix.get("ingredients", [])
            if ing["product_id"] in member_ids
        )

        proposals.append(ConsolidationProposal(
            group_id=group.group_id,
            recommended_suppliers=recommendations,
            estimated_savings_description=_estimate_savings(
                len(member_ids), len(relevant_suppliers), len(benefiting_companies)
            ),
            companies_benefiting=benefiting_companies,
            total_bom_coverage=total_bom_coverage,
        ))

    return proposals


def score_consolidation_benefit(
    current_supplier_count: int,
    proposed_supplier_count: int,
    materials_consolidated: int,
    companies_benefiting: int,
) -> dict:
    """Compute a consolidation benefit score and explanation."""
    if current_supplier_count == 0:
        return {"score": 0.0, "explanation": "No current supplier data"}

    reduction_ratio = max(0, (current_supplier_count - proposed_supplier_count) / current_supplier_count)
    volume_factor = min(1.0, (materials_consolidated * companies_benefiting) / 10)
    score = round((reduction_ratio * 0.6 + volume_factor * 0.4), 3)

    return {
        "score": score,
        "supplier_reduction": f"{current_supplier_count} → {proposed_supplier_count} suppliers",
        "materials_consolidated": materials_consolidated,
        "companies_benefiting": companies_benefiting,
        "explanation": (
            f"Consolidating {materials_consolidated} ingredient(s) across {companies_benefiting} "
            f"company(ies) reduces suppliers from {current_supplier_count} to {proposed_supplier_count} "
            f"(score: {score:.2f}/1.0)."
        ),
    }


def _describe_benefit(covered: int, total: int) -> str:
    if covered >= total:
        return f"Full group coverage: supplies all {total} member ingredient(s) in this category."
    pct = round(covered / total * 100)
    return f"Partial coverage: supplies {covered}/{total} member ingredients ({pct}%). Consider pairing with secondary supplier."


def _assess_risks(coverage_pct: float, materials_covered: int) -> list[str]:
    risks = []
    if coverage_pct >= 0.9:
        risks.append("single_source_risk: high dependency on one supplier for this group")
    if materials_covered == 1:
        risks.append("limited_scope: supplier only covers one material in the group")
    return risks


def _estimate_savings(member_count: int, supplier_count: int, company_count: int) -> str:
    if company_count >= 3 and member_count >= 3:
        return (
            f"High consolidation opportunity: {company_count} companies share {member_count} "
            f"substitutable ingredients. Estimated 15-25% volume discount potential from "
            f"consolidating to {min(2, supplier_count)} preferred supplier(s)."
        )
    if company_count >= 2:
        return (
            f"Medium consolidation opportunity: {company_count} companies share demand. "
            f"Estimated 8-15% volume discount from joint procurement."
        )
    return "Limited consolidation benefit: single-company demand. Focus on supplier quality and lead time."
