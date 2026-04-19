"""Shared cascade state contract."""

from __future__ import annotations

from typing import TypedDict, Any


class CascadeState(TypedDict, total=False):
    intent: str
    budget_eur: float
    catalogue_product: Any
    quantity: int
    strategy: str
    report: dict
    bom: list[dict]
    qualified_agents: dict
    disqualified: list[dict]
    quotes: dict
    final_orders: dict
    logistics_plan: dict
    max_lead_days: int
    total_component_cost: float
    po_count: int
    events: list[dict]


def init_state(intent: str, budget_eur: float, catalogue_product=None, quantity: int = 1, strategy: str = "cost-first") -> CascadeState:
    return {
        "intent": intent,
        "budget_eur": budget_eur,
        "catalogue_product": catalogue_product,
        "quantity": quantity,
        "strategy": strategy,
        "events": [],
    }
