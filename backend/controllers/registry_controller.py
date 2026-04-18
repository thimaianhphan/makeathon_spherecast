from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from pydantic import BaseModel

from backend.schemas import AgentFact, TriggerRequest, LiveMessage, make_id
from backend.services.cascade_service import (
    run_cascade,
    cascade_state,
    prepare_new_cascade,
    simulate_supplier_failure,
    get_latest_substitution_graph,
    get_latest_sourcing_proposal,
)
from backend.services.registry_service import registry
from backend.services.catalogue_service import catalogue_service
from backend.services.db_service import (
    get_all_companies,
    get_all_boms_with_components,
    get_bom_for_product,
    get_raw_materials,
    get_supplier_product_mappings,
    get_cross_company_demand,
)
from backend.config import BUDGET_CEILING_EUR
from backend.services import evidence_store as ev_store

router = APIRouter()


# ── Registry Endpoints ───────────────────────────────────────────────────────

@router.post("/registry/register", status_code=201)
async def register_agent(agent: AgentFact):
    return registry.register(agent)


@router.get("/registry/search")
async def search_agents(
    role: str | None = Query(None),
    capability: str | None = Query(None),
    region: str | None = Query(None),
    certification: str | None = Query(None),
    min_trust: float | None = Query(None),
    include_deprecated: bool = Query(False),
):
    results = registry.search(
        role=role,
        capability=capability,
        region=region,
        certification=certification,
        min_trust=min_trust,
        include_deprecated=include_deprecated,
    )
    return results


@router.get("/registry/list")
async def list_agents():
    return registry.list_all()


@router.get("/api/suppliers")
async def list_suppliers(role: str | None = Query(None)):
    """List all supplier agents (optionally filter by role)."""
    return registry.list_suppliers(role=role)


@router.get("/api/agents")
async def list_agents_protocol():
    """Protocol-ready agent discovery list."""
    return registry.list_protocol_agents()


@router.get("/registry/agent/{agent_id}")
async def get_agent(agent_id: str):
    agent = registry.get(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    return agent


@router.get("/registry/health")
async def registry_health():
    """Return registry filter summary (min_trust, deprecated_agents, regions)."""
    return registry.get_health_filters()


@router.delete("/registry/deregister/{agent_id}", status_code=204)
async def deregister_agent(agent_id: str):
    registry.deregister(agent_id)


@router.post("/registry/log", status_code=201)
async def log_message(msg: LiveMessage):
    registry.log_message(msg)
    return {"status": "logged"}


@router.get("/registry/logs")
async def get_logs():
    return registry.get_messages()


# ── Cascade Trigger ──────────────────────────────────────────────────────────

@router.post("/registry/trigger")
async def trigger_cascade(req: TriggerRequest):
    if cascade_state["running"]:
        return JSONResponse(status_code=409, content={"error": "Cascade already running"})

    # Resolve intent: product_id+quantity or explicit intent
    intent = req.intent
    product = None
    quantity = req.quantity
    budget_eur = req.budget_eur

    if req.product_id and req.quantity > 0:
        product = catalogue_service.get(req.product_id)
        if not product:
            return JSONResponse(status_code=404, content={"error": "Product not found"})
        intent = catalogue_service.get_intent_for_product(product, req.quantity)
        quantity = req.quantity
        if budget_eur == BUDGET_CEILING_EUR:
            budget_eur = product.selling_price_eur * quantity * 1.2

    if not intent:
        intent = "Consolidate ingredient sourcing across all CPG companies"

    prepare_new_cascade()
    asyncio.create_task(
        run_cascade(
            intent,
            budget_eur,
            catalogue_product=product,
            quantity=quantity,
            strategy=req.strategy,
            desired_delivery_date=req.desired_delivery_date,
            company_id=req.company_id,
            focus_category=req.focus_category,
        )
    )
    return {
        "status": "started",
        "intent": intent,
        "product_id": req.product_id,
        "quantity": quantity,
        "company_id": req.company_id,
        "focus_category": req.focus_category,
    }


class SimulateSupplierFailureRequest(BaseModel):
    agent_id: str


@router.post("/api/simulate/supplier-failure")
async def simulate_supplier_failure_endpoint(req: SimulateSupplierFailureRequest):
    """Simulate 'what if supplier fails?' — returns cost/delay delta and alternate supplier."""
    agent_id = req.agent_id
    result = simulate_supplier_failure(agent_id)
    if result is None:
        return JSONResponse(status_code=400, content={"error": "No completed cascade report; run cascade first"})
    if result.get("error"):
        return JSONResponse(status_code=404, content=result)
    return result


@router.post("/registry/disrupt/{agent_id}")
async def disrupt_agent(agent_id: str):
    agent = registry.get(agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})

    msg = LiveMessage(
        message_id=make_id("alert"),
        from_id=agent_id,
        from_label=agent.name,
        to_id="agnes-01",
        to_label="Agnes",
        type="disruption_alert",
        summary=f"DISRUPTION: {agent.name} reports supply issue",
        detail="Manual disruption triggered via API",
        color="#F44336",
        icon="alert",
    )
    registry.log_message(msg)
    return {"status": "disruption_triggered", "agent_id": agent_id}


# ── New CPG Data Endpoints ────────────────────────────────────────────────────

@router.get("/api/companies")
async def list_companies():
    """Return all companies from the SQLite database."""
    try:
        return get_all_companies()
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve companies"})


@router.get("/api/boms")
async def list_boms(company_id: int | None = Query(None)):
    """Return all BOMs, optionally filtered by company."""
    try:
        boms = get_all_boms_with_components()
        if company_id is not None:
            boms = [b for b in boms if b.get("produced_product", {}).get("company_id") == company_id]
        return boms
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve BOMs"})


@router.get("/api/boms/{product_id}")
async def get_bom(product_id: int):
    """Return the BOM for a specific finished good."""
    try:
        bom = get_bom_for_product(product_id)
        if not bom:
            return JSONResponse(status_code=404, content={"error": "BOM not found for product"})
        return bom
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve BOM"})


@router.get("/api/raw-materials")
async def list_raw_materials():
    """Return all raw materials with their supplier mappings."""
    try:
        raw_materials = get_raw_materials()
        supplier_mappings = get_supplier_product_mappings()
        sup_map: dict[int, list] = {}
        for m in supplier_mappings:
            sup_map.setdefault(m["product_id"], []).append({
                "supplier_id": m["supplier_id"],
                "supplier_name": m["supplier_name"],
            })
        for rm in raw_materials:
            rm["suppliers"] = sup_map.get(rm["Id"], [])
        return raw_materials
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve raw materials"})


@router.get("/api/substitutions")
async def get_substitution_graph():
    """Return the latest substitution graph from the most recent cascade."""
    graph = get_latest_substitution_graph()
    if not graph:
        return JSONResponse(status_code=404, content={"error": "No substitution graph available. Run cascade first."})
    return {k: v.model_dump() for k, v in graph.items()}


@router.get("/api/proposal")
async def get_sourcing_proposal():
    """Return the latest consolidated sourcing proposal."""
    proposal = get_latest_sourcing_proposal()
    if not proposal:
        return JSONResponse(status_code=404, content={"error": "No sourcing proposal available. Run cascade first."})
    return [p.model_dump() for p in proposal]


@router.get("/api/demand")
async def get_cross_company_demand_endpoint():
    """Return cross-company ingredient demand aggregation."""
    try:
        return get_cross_company_demand()
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve demand data"})


# ── Evidence Trail Endpoints ──────────────────────────────────────────────────

@router.get("/api/evidence")
async def list_evidence(
    source_type: str | None = Query(None),
    claim: str | None = Query(None),
):
    """List all recorded evidence items with optional filters."""
    if claim:
        items = ev_store.get_by_claim(claim)
    else:
        items = ev_store.list_all(source_type=source_type)
    return [e.model_dump() for e in items]


@router.get("/api/evidence/{evidence_id}")
async def get_evidence(evidence_id: str):
    """Fetch a single evidence item by ID."""
    item = ev_store.get_by_id(evidence_id)
    if not item:
        return JSONResponse(status_code=404, content={"error": "Evidence item not found"})
    return item.model_dump()
