"""
Tradeoff sub-agent — pure Python, no LLM.

Scores each post-compliance candidate on five dimensions and returns a
ranked list. Tune the weights via TRADEOFF_WEIGHTS.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.schemas import SubstitutionCandidate, SupplierEvidence, TradeoffSummary

# ── Tunable weights (sum to 1.0) ────────────────────────────────────────────
TRADEOFF_WEIGHTS: dict[str, float] = {
    "cost": 0.35,
    "lead_time": 0.20,
    "single_source_risk": 0.20,
    "compliance_confidence": 0.15,
    "consolidation": 0.10,
}


@dataclass
class ScoredCandidate:
    candidate: SubstitutionCandidate
    composite_score: float
    cost_impact: str
    estimated_savings_pct: float | None
    best_supplier_evidence: SupplierEvidence | None
    recommended_supplier_id: int | None
    score_breakdown: dict[str, float]


def rank_candidates(
    candidates: list[SubstitutionCandidate],
    supplier_evidence: list[SupplierEvidence],
    cross_company_demand: list[dict],
    original_product_id: int,
) -> list[ScoredCandidate]:
    """
    Score and rank candidates. Only viable candidates (overall_viable=True) are scored.
    Returns sorted descending by composite_score; may be empty.
    """
    demand_map = {d["product_id"]: d for d in cross_company_demand}
    # Map candidate_product_id → list of evidence records
    ev_map: dict[int, list[SupplierEvidence]] = {}
    for ev in supplier_evidence:
        ev_map.setdefault(ev.candidate_product_id, []).append(ev)

    scored: list[ScoredCandidate] = []
    for cand in candidates:
        if not cand.overall_viable:
            continue
        ev_list = ev_map.get(cand.substitute_product_id, [])
        sc = _score_candidate(cand, ev_list, demand_map)
        scored.append(sc)

    scored.sort(key=lambda x: x.composite_score, reverse=True)
    return scored


def _score_candidate(
    cand: SubstitutionCandidate,
    ev_list: list[SupplierEvidence],
    demand_map: dict[int, dict],
) -> ScoredCandidate:
    best_ev = _best_evidence(ev_list)
    supplier_count = len({e.supplier_id for e in ev_list if e.source_type != "no_evidence"})

    # ── Cost dimension (0–1, higher = better savings) ───────────────────────
    cost_score, cost_impact, savings_pct = _score_cost(best_ev)

    # ── Lead-time dimension (0–1, higher = shorter lead time) ───────────────
    lead_score = _score_lead_time(best_ev)

    # ── Single-source risk (0–1, higher = less risk) ─────────────────────────
    risk_score = min(supplier_count / 2.0, 1.0)  # 0 suppliers=0, 1=0.5, ≥2=1.0

    # ── Compliance confidence (0–1, avg of check confidences) ───────────────
    compliance_score = _score_compliance(cand)

    # ── Consolidation bonus (0–1) ────────────────────────────────────────────
    demand_info = demand_map.get(cand.substitute_product_id, {})
    bom_count = demand_info.get("bom_count", 0)
    consolidation_score = min(bom_count / 5.0, 1.0)  # 5+ BOMs = full score

    breakdown = {
        "cost": cost_score,
        "lead_time": lead_score,
        "single_source_risk": risk_score,
        "compliance_confidence": compliance_score,
        "consolidation": consolidation_score,
    }

    composite = sum(
        TRADEOFF_WEIGHTS[k] * v for k, v in breakdown.items()
    )

    # Attach tradeoff summary back onto the candidate
    compliance_risk = "approved"
    risk_notes = ""
    if cand.eu_compliance:
        compliance_risk = cand.eu_compliance.overall_status
        risk_notes = "; ".join(cand.eu_compliance.blocking_issues)

    consolidation_note = (
        f"Candidate appears in {bom_count} BOM(s) across "
        f"{demand_info.get('company_count', 0)} company/ies — consolidation opportunity."
        if bom_count > 1 else "No cross-BOM consolidation benefit detected."
    )

    cand.tradeoffs = TradeoffSummary(
        cost_impact=cost_impact,
        supplier_consolidation_benefit=consolidation_note,
        lead_time_impact=(
            f"{best_ev.lead_time_days} days" if best_ev and best_ev.lead_time_days
            else "Lead time unknown"
        ),
        compliance_risk=compliance_risk,
        risk_notes=risk_notes,
        evidence_confidence_avg=_avg_evidence_confidence(ev_list),
        external_evidence_ratio=_external_ratio(ev_list),
    )

    recommended_supplier_id = (
        best_ev.supplier_id
        if best_ev and best_ev.source_type != "no_evidence"
        else None
    )

    return ScoredCandidate(
        candidate=cand,
        composite_score=round(composite, 4),
        cost_impact=cost_impact,
        estimated_savings_pct=savings_pct,
        best_supplier_evidence=best_ev,
        recommended_supplier_id=recommended_supplier_id,
        score_breakdown=breakdown,
    )


def _best_evidence(ev_list: list[SupplierEvidence]) -> SupplierEvidence | None:
    real = [e for e in ev_list if e.source_type != "no_evidence"]
    if not real:
        return None
    # Prefer supplier_site > cert_db > aggregator > news; then by confidence
    order = {"supplier_site": 0, "cert_db": 1, "aggregator": 2, "news": 3}
    return min(real, key=lambda e: (order.get(e.source_type, 9), -e.confidence))


def _score_cost(ev: SupplierEvidence | None) -> tuple[float, str, float | None]:
    if ev is None or ev.unit_price_eur is None:
        return 0.5, "unknown", None  # neutral score when data missing
    # Without original price, we can only note the absolute price
    impact_str = f"~€{ev.unit_price_eur:.4f}/unit (estimated from web)"
    return 0.6, impact_str, None  # can't compute % without original price


def _score_lead_time(ev: SupplierEvidence | None) -> float:
    if ev is None or ev.lead_time_days is None:
        return 0.5  # neutral
    if ev.lead_time_days <= 14:
        return 1.0
    if ev.lead_time_days <= 30:
        return 0.75
    if ev.lead_time_days <= 60:
        return 0.5
    return 0.25


def _score_compliance(cand: SubstitutionCandidate) -> float:
    if not cand.eu_compliance or not cand.eu_compliance.checks:
        return 0.4
    return sum(c.confidence for c in cand.eu_compliance.checks) / len(cand.eu_compliance.checks)


def _avg_evidence_confidence(ev_list: list[SupplierEvidence]) -> float:
    real = [e for e in ev_list if e.source_type != "no_evidence"]
    if not real:
        return 0.0
    return round(sum(e.confidence for e in real) / len(real), 3)


def _external_ratio(ev_list: list[SupplierEvidence]) -> float:
    if not ev_list:
        return 0.0
    external = [e for e in ev_list if e.source_type in ("supplier_site", "cert_db", "news", "aggregator")]
    return round(len(external) / len(ev_list), 3)
