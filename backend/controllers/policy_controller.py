"""Policy controller — policy spec and evaluation endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.policy_service import policy_service

router = APIRouter()


@router.get("/api/policy")
async def get_policy():
    """Get current policy spec."""
    return policy_service.get_policy()


@router.post("/api/policy/evaluate")
async def evaluate_policy(plan: dict):
    """Evaluate a plan against current policy."""
    result = policy_service.evaluate_policy(plan)
    return result
