"""Escalation controller — human response to trust/risk escalation."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.schemas import EscalationResponse
from backend.services.cascade_service import respond_to_escalation, cascade_state

router = APIRouter()


@router.post("/api/escalation/respond")
async def escalation_respond(req: EscalationResponse):
    """Human responds to escalation: proceed, reject, or substitute_agent."""
    ok = respond_to_escalation(req.escalation_id, req.action)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Escalation not found or already resolved"})
    return {"status": "ok", "action": req.action, "escalation_id": req.escalation_id}


@router.get("/api/escalation/status")
async def escalation_status():
    """Get current escalation status (for frontend polling)."""
    return {"paused": cascade_state.get("paused", False), "escalation": cascade_state.get("escalation")}
