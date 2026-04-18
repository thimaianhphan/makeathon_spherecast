"""Probabilistic event engine for cascade dynamics."""

from __future__ import annotations

import random


EVENT_CATALOG = {
    "pre_quotes": [
        {"type": "raw_material_shortage", "probability": 0.18, "impact": {"price_pct": (2, 7)}},
        {"type": "capacity_slack", "probability": 0.12, "impact": {"price_pct": (-3, -1)}},
    ],
    "post_logistics": [
        {"type": "port_delay", "probability": 0.18, "impact": {"lead_time_days": (3, 7)}},
        {"type": "route_optimization", "probability": 0.10, "impact": {"lead_time_days": (-2, -1), "logistics_cost_pct": (-5, -2)}},
    ],
}


def _roll(probability: float) -> bool:
    return random.random() < probability


def trigger_events(stage: str) -> list[dict]:
    events = []
    for spec in EVENT_CATALOG.get(stage, []):
        if _roll(spec["probability"]):
            impact = {}
            for key, (low, high) in spec["impact"].items():
                impact[key] = random.randint(low, high) if "days" in key else random.uniform(low, high)
            events.append({"type": spec["type"], "stage": stage, "impact": impact})
    return events


def apply_quote_impacts(quotes: dict, events: list[dict]) -> None:
    for ev in events:
        if "price_pct" in ev["impact"]:
            pct = ev["impact"]["price_pct"]
            for q in quotes.values():
                q["initial_price"] = round(q["initial_price"] * (1 + pct / 100), 2)


def apply_logistics_impacts(logistics_plan: dict, events: list[dict]) -> None:
    for ev in events:
        impact = ev["impact"]
        if "logistics_cost_pct" in impact:
            logistics_plan["total_logistics_cost_eur"] = round(
                logistics_plan["total_logistics_cost_eur"] * (1 + impact["logistics_cost_pct"] / 100), 2
            )
        if "lead_time_days" in impact:
            logistics_plan["critical_path_days"] += int(impact["lead_time_days"])
