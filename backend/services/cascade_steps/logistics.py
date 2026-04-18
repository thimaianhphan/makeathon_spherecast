"""Cascade step: logistics."""

from __future__ import annotations

from backend.services.logistics_service import plan_logistics


def run_logistics(final_orders: dict, emit) -> tuple[dict, int]:
    logistics_plan, max_lead_days = plan_logistics(final_orders, emit)
    return logistics_plan, max_lead_days
