"""
Judge gate — the final compliance + quality gate for one raw-material pipeline.

Encoding the trust hierarchy (highest to lowest):
  1. Regulatory / certification database confirmations
  2. Supplier official website / spec sheet
  3. Reputable news, trade publications
  4. LLM inference without external support

When evidence conflicts, higher-tier evidence wins.
When tiers tie, prefer the more recent source.

Decisions:
  accept       — compliance confidence ≥ 0.8 on ALL checks, at least one non-inferred
                 evidence item backing compliance, positive or neutral cost outlook.
  needs_review — ≥ 1 check is 'uncertain', OR cost advantage is unknown/marginal,
                 OR all evidence is LLM inference. Flags what the human must verify.
  reject       — any compliance check is 'fail', OR no viable candidates remain.
"""

from __future__ import annotations

from backend.schemas import SupplierEvidence
from backend.services.sourcing.prompts import JUDGE_REASONING_PROMPT
from backend.services.sourcing.subagents.tradeoff import ScoredCandidate

MIN_ACCEPT_CONFIDENCE = 0.8
MARGINAL_SAVINGS_THRESHOLD = 0.02  # < 2% savings = marginal


async def adjudicate(
    scored_candidates: list[ScoredCandidate],
    original_name: str,
) -> tuple[str, str, list[str]]:
    """
    Returns (decision, reasoning, flags_for_human).
    decision ∈ {"accept", "needs_review", "reject"}
    """
    if not scored_candidates:
        reasoning = await _generate_reasoning(
            decision="reject",
            original_name=original_name,
            candidate_name="none",
            compliance_status="no viable candidates",
            evidence_sources="none",
            flags="No functionally equivalent candidates found in catalog.",
        )
        return "reject", reasoning, ["No viable substitute candidates identified in catalog."]

    best = scored_candidates[0]
    cand = best.candidate
    compliance = cand.eu_compliance

    flags: list[str] = []

    # ── Hard reject conditions ───────────────────────────────────────────────
    if compliance:
        for check in compliance.checks:
            if check.status == "fail":
                flags.append(
                    f"Compliance FAIL [{check.check}]: {check.reasoning[:120]}"
                )
        if flags:
            reasoning = await _generate_reasoning(
                decision="reject",
                original_name=original_name,
                candidate_name=cand.substitute_name,
                compliance_status=compliance.overall_status,
                evidence_sources=_summarise_sources(best.best_supplier_evidence),
                flags="; ".join(flags),
            )
            return "reject", reasoning, flags

    # ── Check if all evidence is inferred (no external backing) ─────────────
    all_inferred = _all_inferred(cand, best.best_supplier_evidence)

    # ── Evaluate accept conditions ───────────────────────────────────────────
    accept = True
    if not compliance or not compliance.checks:
        flags.append("No compliance assessment available — full human review required.")
        accept = False
    else:
        for check in compliance.checks:
            if check.status == "uncertain":
                flags.append(
                    f"Uncertain compliance [{check.check}]: {check.reasoning[:120]}"
                )
                accept = False
            elif check.confidence < MIN_ACCEPT_CONFIDENCE:
                flags.append(
                    f"Low confidence [{check.check}]: {check.confidence:.2f} — "
                    "verify with supplier documentation."
                )
                accept = False

    if all_inferred:
        flags.append(
            "All compliance evidence is LLM inference — no supplier documentation fetched. "
            "Obtain spec sheet before proceeding."
        )
        accept = False

    if best.estimated_savings_pct is not None and best.estimated_savings_pct < MARGINAL_SAVINGS_THRESHOLD:
        flags.append(
            f"Estimated savings ({best.estimated_savings_pct:.1%}) below "
            f"{MARGINAL_SAVINGS_THRESHOLD:.0%} threshold — marginal benefit."
        )
        accept = False

    if best.best_supplier_evidence and best.best_supplier_evidence.red_flags:
        for rf in best.best_supplier_evidence.red_flags:
            flags.append(f"Supplier red flag: {rf}")
        accept = False

    decision = "accept" if accept else "needs_review"
    reasoning = await _generate_reasoning(
        decision=decision,
        original_name=original_name,
        candidate_name=cand.substitute_name,
        compliance_status=compliance.overall_status if compliance else "unknown",
        evidence_sources=_summarise_sources(best.best_supplier_evidence),
        flags="; ".join(flags) if flags else "None",
    )
    return decision, reasoning, flags


async def _generate_reasoning(
    decision: str,
    original_name: str,
    candidate_name: str,
    compliance_status: str,
    evidence_sources: str,
    flags: str,
) -> str:
    from backend.services.agent_service import ai_reason

    prompt = JUDGE_REASONING_PROMPT.format(
        original_name=original_name,
        decision=decision,
        candidate_name=candidate_name,
        compliance_status=compliance_status,
        evidence_sources=evidence_sources,
        flags=flags,
    )
    try:
        return await ai_reason("AgnesJudge", "sourcing_judge", prompt)
    except Exception:
        return (
            f"Decision: {decision}. Candidate: {candidate_name}. "
            f"Compliance: {compliance_status}. Flags: {flags}"
        )


def _all_inferred(cand, best_ev: SupplierEvidence | None) -> bool:
    """True if no non-inferred evidence exists anywhere in the candidate's trail."""
    if best_ev and best_ev.source_type != "no_evidence":
        return False
    if cand.evidence_trail:
        for ev in cand.evidence_trail:
            if ev.source_type != "llm_inference":
                return False
    if cand.eu_compliance:
        for check in cand.eu_compliance.checks:
            if check.source in ("enriched", "database"):
                return False
    return True


def _summarise_sources(ev: SupplierEvidence | None) -> str:
    if ev is None or ev.source_type == "no_evidence":
        return "no external evidence"
    urls = ", ".join(ev.source_urls[:2]) or "no URLs"
    return f"{ev.source_type} ({ev.supplier_name}): {urls}"
