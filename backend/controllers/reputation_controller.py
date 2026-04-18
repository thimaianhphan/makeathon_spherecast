from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.schemas import TrustSubmission
from backend.services.trust_service import reputation_ledger

router = APIRouter()


# ── Reputation Endpoints ────────────────────────────────────────────────────

@router.post("/api/trust/submit", status_code=201)
async def submit_trust_rating(submission: TrustSubmission):
    """Submit contextual trust rating (weighted by rater's own trust)."""
    return reputation_ledger.submit_trust_rating(submission)


@router.get("/api/trust/contextual/{agent_id}")
async def get_contextual_score(agent_id: str, dimension: str | None = None):
    """Get contextual trust scores for agent (optionally filter by dimension)."""
    return reputation_ledger.get_contextual_score(agent_id, dimension)


@router.get("/api/reputation/summary")
async def reputation_summary():
    return reputation_ledger.get_summary()


@router.get("/api/reputation/scores")
async def reputation_scores():
    return [s.model_dump() for s in reputation_ledger.get_all_scores()]


@router.get("/api/reputation/agent/{agent_id}")
async def reputation_agent(agent_id: str):
    score = reputation_ledger.get_score(agent_id)
    if not score:
        return JSONResponse(status_code=404, content={"error": "No reputation data"})
    chain = reputation_ledger.verify_chain(agent_id)
    attestations = reputation_ledger.get_attestations(agent_id)
    return {
        "score": score.model_dump(),
        "chain_verification": chain,
        "attestations": [a.model_dump() for a in attestations[-10:]],
    }
