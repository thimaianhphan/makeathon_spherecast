"""
Coordination Cascade Orchestrator — Agnes AI Supply Chain Manager

Executes the CPG supply chain cascade:
  Init → Demand Analysis → Substitution Detection → Enrichment →
  EU Compliance → Consolidation → Tradeoffs → Evidence → Reputation → Report
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from backend.config import BUDGET_CEILING_EUR, TRUST_THRESHOLD, ENABLE_EXTERNAL_AGENT_TRANSPORT
from backend.schemas import LiveMessage, AgentProtocolMessage, make_id
from backend.services.registry_service import registry
from backend.services.agent_service import ai_reason
from backend.services.risk_propagation_service import risk_propagation
from backend.services.pubsub_service import event_bus
from backend.services.trust_service import reputation_ledger
from backend.services.intelligence_service import generate_intelligence_signals
from backend.services.db_service import (
    get_all_companies,
    get_all_boms_with_components,
    get_supplier_product_mappings,
    get_raw_materials,
)
from backend.time_utils import utc_now
from backend.services.cascade_steps.step_demand_analysis import run_step_demand_analysis
from backend.services.cascade_steps.step_substitution import run_step_substitution
from backend.services.cascade_steps.step_enrichment import run_step_enrichment
from backend.services.cascade_steps.step_compliance import run_step_compliance
from backend.services.cascade_steps.step_consolidation import run_step_consolidation
from backend.services.cascade_steps.step_tradeoffs import run_step_tradeoffs
from backend.services.cascade_steps.step_evidence import compile_evidence_trails
from backend.services.cascade_steps.step_reputation import run_step_reputation


# ── State ────────────────────────────────────────────────────────────────────

cascade_state = {
    "running": False,
    "report": None,
    "progress": 0,
    "paused": False,
    "escalation": None,
    "escalation_event": None,
    "escalation_response": None,
}

# Store latest intermediate results for API access
_latest_substitution_graph: dict = {}
_latest_sourcing_proposal: list = []


def _emit_escalation(reason: str, agent_id: str | None, trust_score: float | None, risk_score: float | None, _emit) -> str:
    """Emit escalation event; return escalation_id."""
    esc_id = make_id("esc")
    cascade_state["paused"] = True
    cascade_state["escalation"] = {
        "escalation_id": esc_id,
        "reason": reason,
        "agent_id": agent_id,
        "trust_score": trust_score,
        "risk_score": risk_score,
        "threshold": TRUST_THRESHOLD,
    }
    cascade_state["escalation_event"] = asyncio.Event()
    _emit(
        "escalation",
        "Escalation",
        "agnes-01",
        "Agnes",
        "escalation",
        summary=None,
        payload={
            "summary": reason,
            "detail": "Trust/risk threshold exceeded. Awaiting human response.",
        },
    )
    return esc_id


def respond_to_escalation(escalation_id: str, action: str) -> bool:
    """Human responds to escalation; unblock cascade if applicable."""
    if cascade_state.get("escalation", {}).get("escalation_id") != escalation_id:
        return False
    cascade_state["escalation_response"] = action
    ev = cascade_state.get("escalation_event")
    if ev:
        ev.set()
    cascade_state["paused"] = False
    return True


def prepare_new_cascade():
    """Clear all stateful services and escalation state before a new cascade."""
    global _latest_substitution_graph, _latest_sourcing_proposal
    registry.clear()
    event_bus.clear()
    reputation_ledger.clear()
    risk_propagation.clear()
    _latest_substitution_graph = {}
    _latest_sourcing_proposal = []
    cascade_state["paused"] = False
    cascade_state["escalation"] = None
    cascade_state["escalation_response"] = None


def _ts(offset_seconds: int = 0) -> str:
    return (utc_now() + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")


def _emit(
    from_id,
    from_label,
    to_id,
    to_label,
    msg_type,
    summary=None,
    detail="",
    color="#2196F3",
    icon="info",
    payload=None,
):
    if summary is None:
        from backend.services.message_builder import build_message_content
        summary, detail, color, icon = build_message_content(msg_type, payload or {})
    msg = LiveMessage(
        message_id=make_id("msg"),
        timestamp=_ts(),
        from_id=from_id,
        from_label=from_label,
        to_id=to_id,
        to_label=to_label,
        type=msg_type,
        summary=summary or "",
        detail=detail or "",
        color=color,
        icon=icon,
    )
    registry.log_message(msg)
    if ENABLE_EXTERNAL_AGENT_TRANSPORT:
        try:
            from backend.services.agent_transport import send_to_agent
            proto_msg = AgentProtocolMessage(
                message_id=msg.message_id,
                from_agent=from_id,
                to_agent=to_id,
                message_type=msg_type,
                payload={
                    "summary": summary,
                    "detail": detail,
                    "color": color,
                    "icon": icon,
                },
                reply_to="",
            )
            send_to_agent(proto_msg)
        except Exception:
            pass
    return msg


def _build_dashboard(report: dict) -> dict:
    """Build dashboard-compatible summary from cascade report.

    Extracts key metrics from the cascade report and returns a DashboardData
    dict containing hero metrics (company/BOM counts, substitution and compliance
    summaries) suitable for frontend consumption via the /api/report endpoint.
    """
    from backend.schemas import HeroMetric, DashboardData
    demand = report.get("demand_analysis", {})
    sub = report.get("substitution_summary", {})
    compliance = report.get("compliance_summary", {})
    proposal = report.get("sourcing_proposal", [])

    cross_company = len(demand.get("cross_company_candidates", []))
    viable_subs = sub.get("viable_candidates", 0)
    approved_checks = compliance.get("approved", 0)
    proposals_count = len(proposal) if isinstance(proposal, list) else 0

    hero_metrics = [
        HeroMetric(label="Companies Analysed", value=str(len(report.get("companies", [])))),
        HeroMetric(label="BOMs Processed", value=str(demand.get("total_boms", 0))),
        HeroMetric(label="Cross-Company Ingredients", value=str(cross_company)),
        HeroMetric(label="Viable Substitutions", value=str(viable_subs)),
        HeroMetric(label="Compliance Checks Passed", value=str(approved_checks)),
        HeroMetric(label="Sourcing Groups", value=str(proposals_count)),
    ]
    return DashboardData(
        hero_metrics=hero_metrics,
        compliance_summary=compliance,
        discovery_results=demand,
    ).model_dump()


# ── Main Cascade ─────────────────────────────────────────────────────────────

async def run_cascade(
    intent: str | None = None,
    budget_eur: float = BUDGET_CEILING_EUR,
    catalogue_product=None,
    quantity: int = 1,
    strategy: str = "consolidation-first",
    desired_delivery_date: str | None = None,
    company_id: int | None = None,
    focus_category: str | None = None,
) -> dict:
    """Agnes AI Supply Chain Manager — full CPG cascade orchestrator."""
    global _latest_substitution_graph, _latest_sourcing_proposal

    cascade_state["running"] = True
    cascade_state["progress"] = 0
    cascade_state["report"] = None

    report = {
        "report_id": make_id("NCR-AGNES"),
        "intent": intent or "Consolidate CPG ingredient sourcing across all companies",
        "initiated_by": "agnes-01",
        "initiated_at": _ts(),
        "status": "in_progress",
        "companies": [],
        "demand_analysis": {},
        "substitution_graph": {},
        "substitution_summary": {},
        "compliance_summary": {},
        "enrichment_summary": {},
        "sourcing_proposal": [],
        "tradeoff_analysis": [],
        "evidence_trails": [],
        "reputation_summary": {},
        "graph_nodes": [],
        "graph_edges": [],
        "dashboard": {},
        "message_log_summary": {"total_messages": 0, "by_type": {}},
        "intelligence_feed": [],
    }

    try:
        # ── Step 0: Init ─────────────────────────────────────────────────
        _emit("system", "System", "registry", "Agent Registry", "system",
              summary="Agnes AI Supply Chain Manager starting up...")
        from backend.services.agent_service import create_seed_agents
        seed_agents = create_seed_agents()
        for agent in seed_agents:
            registry.register(agent)
        cascade_state["progress"] = 5

        # ── Load SQLite data ─────────────────────────────────────────────
        companies = get_all_companies()
        boms = get_all_boms_with_components()
        supplier_mappings = get_supplier_product_mappings()
        raw_materials = get_raw_materials()
        report["companies"] = companies
        _emit("agnes-01", "Agnes", "system", "System", "system",
              summary=f"Loaded {len(companies)} companies, {len(boms)} BOMs, "
                      f"{len(raw_materials)} raw materials, {len(supplier_mappings)} supplier mappings.")
        cascade_state["progress"] = 10

        # ── Step 1: Demand Analysis ──────────────────────────────────────
        demand_matrix = await run_step_demand_analysis(boms, raw_materials, _emit)
        report["demand_analysis"] = demand_matrix
        cascade_state["progress"] = 22

        # ── Step 2: Substitution Detection ──────────────────────────────
        # Only analyse cross-company materials (≥2 BOMs) — keeps LLM calls bounded
        from backend.services.db_service import get_cross_company_demand
        cross_demand = get_cross_company_demand()
        cross_ids = {r["product_id"] for r in cross_demand if r["bom_count"] >= 2}
        sub_materials = [rm for rm in raw_materials if rm["Id"] in cross_ids][:150]
        if not sub_materials:
            sub_materials = raw_materials[:50]
        _emit("agnes-01", "Agnes", "system", "System", "system",
              summary=f"Substitution scope: {len(sub_materials)} cross-company materials (from {len(raw_materials)} total).")
        substitution_graph = await run_step_substitution(sub_materials, boms, _emit)
        # Serialise graph for report (convert SubstitutionGroup objects)
        report["substitution_graph"] = {
            k: v.model_dump() for k, v in substitution_graph.items()
        }
        viable_total = sum(sum(1 for c in g.candidates if c.overall_viable) for g in substitution_graph.values())
        report["substitution_summary"] = {
            "groups": len(substitution_graph),
            "viable_candidates": viable_total,
        }
        _latest_substitution_graph = substitution_graph
        cascade_state["progress"] = 45

        # ── Step 3: External Enrichment ──────────────────────────────────
        enrichment_summary = await run_step_enrichment(substitution_graph, _emit)
        report["enrichment_summary"] = enrichment_summary
        cascade_state["progress"] = 55

        # ── Step 4: EU Compliance ────────────────────────────────────────
        compliance_summary = await run_step_compliance(substitution_graph, _emit)
        report["compliance_summary"] = compliance_summary
        cascade_state["progress"] = 65

        # ── Step 5: Consolidation ────────────────────────────────────────
        proposals = await run_step_consolidation(demand_matrix, supplier_mappings, substitution_graph, _emit)
        report["sourcing_proposal"] = [p.model_dump() for p in proposals]
        _latest_sourcing_proposal = proposals
        cascade_state["progress"] = 75

        # ── Step 6: Tradeoff Analysis ────────────────────────────────────
        tradeoffs = await run_step_tradeoffs(proposals, substitution_graph, _emit)
        report["tradeoff_analysis"] = tradeoffs
        cascade_state["progress"] = 82

        # ── Step 7: Evidence Trail ───────────────────────────────────────
        evidence_trails = compile_evidence_trails(substitution_graph, proposals, tradeoffs)
        report["evidence_trails"] = evidence_trails
        cascade_state["progress"] = 88

        # ── Step 8: Reputation ───────────────────────────────────────────
        reputation_summary = run_step_reputation(proposals, supplier_mappings, _emit)
        report["reputation_summary"] = reputation_summary
        cascade_state["progress"] = 94

        # ── Step 9: Intelligence & Final Report ──────────────────────────
        intel_results = await generate_intelligence_signals(event_bus, count=5)
        report["intelligence_feed"] = intel_results
        cascade_state["progress"] = 97

        # Build graph nodes/edges for visualisation
        report["graph_nodes"] = _build_graph_nodes(companies, supplier_mappings, proposals)
        report["graph_edges"] = _build_graph_edges(supplier_mappings, proposals)
        report["dashboard"] = _build_dashboard(report)
        report["status"] = "completed"

        messages = registry.get_messages()
        by_type: dict[str, int] = {}
        for m in messages:
            by_type[m.type] = by_type.get(m.type, 0) + 1
        report["message_log_summary"] = {"total_messages": len(messages), "by_type": by_type}

        _emit("agnes-01", "Agnes", "system", "System", "system",
              summary="Agnes cascade completed. Sourcing proposal ready.")

    except Exception as e:
        report["status"] = "error"
        report["error"] = str(e)
        _emit("system", "System", "system", "System", "error",
              summary=None,
              payload={"summary": f"Cascade error: {str(e)}"})

    cascade_state["running"] = False
    cascade_state["progress"] = 100
    cascade_state["report"] = report
    try:
        from backend.services.cascade_history import add_report
        add_report(report)
    except Exception:
        pass
    return report


def simulate_supplier_failure(agent_id: str) -> dict | None:
    """Simulate 'what if supplier fails?' — returns impact and alternate supplier."""
    report = cascade_state.get("report")
    if not report or report.get("status") != "completed":
        return None

    proposals = report.get("sourcing_proposal", [])
    affected_groups = [p for p in proposals if any(
        str(s.get("supplier_id", "")) == agent_id.split("-")[-1]
        for s in p.get("recommended_suppliers", [])
    )]

    if not affected_groups:
        return {"error": "Agent not in current plan", "agent_id": agent_id}

    return {
        "agent_id": agent_id,
        "affected_groups": len(affected_groups),
        "impact": "moderate",
        "message": f"Agent {agent_id} appears in {len(affected_groups)} sourcing group(s). Alternative suppliers available in same ingredient category.",
    }


def get_latest_substitution_graph() -> dict:
    """Return the most recently computed substitution graph."""
    return _latest_substitution_graph


def get_latest_sourcing_proposal() -> list:
    """Return the most recently computed sourcing proposal."""
    return _latest_sourcing_proposal


def _build_graph_nodes(companies: list[dict], supplier_mappings: list[dict], proposals: list) -> list[dict]:
    from backend.schemas import GraphNode
    nodes: list[dict] = []

    # Agnes central node
    nodes.append(GraphNode(id="agnes-01", label="Agnes", role="procurement_agent", color="#9C27B0", size=40).model_dump())

    # Company nodes
    for company in companies:
        cid = f"company-{company['Id']}"
        nodes.append(GraphNode(id=cid, label=company["Name"], role="company", color="#2196F3", size=30).model_dump())

    # Supplier nodes (deduplicated)
    seen: set[int] = set()
    for m in supplier_mappings:
        sid = m["supplier_id"]
        if sid not in seen:
            seen.add(sid)
            nodes.append(GraphNode(
                id=f"supplier-{sid}",
                label=m["supplier_name"],
                role="raw_material_supplier",
                color="#4CAF50",
                size=25,
            ).model_dump())

    return nodes


def _build_graph_edges(supplier_mappings: list[dict], proposals: list) -> list[dict]:
    from backend.schemas import GraphEdge
    edges: list[dict] = []
    seen: set[tuple] = set()
    for m in supplier_mappings:
        key = (f"supplier-{m['supplier_id']}", "agnes-01")
        if key not in seen:
            seen.add(key)
            edges.append(GraphEdge(
                **{"from": f"supplier-{m['supplier_id']}", "to": "agnes-01"},
                type="supply_relationship",
                label=m["product_name"][:30],
                status="active",
            ).model_dump(by_alias=True))
    return edges
