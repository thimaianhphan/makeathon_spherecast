"""Logistics planning service."""

from __future__ import annotations

import random

from backend.services.registry_service import registry


def plan_logistics(final_orders: dict, emit, logistics_agent_id: str = "dhl-logistics-01") -> tuple[dict, int]:
    logistics_agent = registry.get(logistics_agent_id)
    shipments = []
    total_logistics_cost = 0
    max_lead_days = 0
    bottleneck_product = ""
    bottleneck_supplier = ""

    for _, order in final_orders.items():
        agent = order["agent"]
        if agent.trust and agent.trust.ferrari_tier_status == "internal":
            continue  # no shipping needed for internal

        origin = agent.location.headquarters if agent.location else None
        if not origin:
            continue

        distance_km = random.randint(80, 600)
        cost = round(distance_km * random.uniform(3.5, 8.5), 2)
        total_logistics_cost += cost

        emit(
            agent.agent_id,
            agent.name,
            logistics_agent_id,
            logistics_agent.name if logistics_agent else "Logistics Provider",
            "logistics_request",
            summary=None,
            payload={
                "product_name": order["product"].name,
                "origin": f"{origin.city}, {origin.country}",
                "quantity": order["quantity"],
            },
        )

        duration_hours = round(distance_km / 65, 1)
        emit(
            logistics_agent_id,
            logistics_agent.name if logistics_agent else "Logistics Provider",
            agent.agent_id,
            agent.name,
            "logistics_proposal",
            summary=None,
            payload={
                "route": f"{origin.city} → Maranello, {distance_km}km",
                "cost_eur": cost,
                "duration_hours": duration_hours,
            },
        )

        lead_days = order["product"].lead_time_days
        if lead_days > max_lead_days:
            max_lead_days = lead_days
            bottleneck_product = order["product"].name
            bottleneck_supplier = agent.name

        shipments.append(
            {
                "shipment_id": f"SHIP-{len(shipments) + 1:03d}",
                "from_agent": agent.agent_id,
                "from_name": agent.name,
                "from_location": f"{origin.city}, {origin.country}",
                "to_location": "Maranello, IT",
                "cargo": order["product"].name,
                "mode": "road",
                "distance_km": distance_km,
                "cost_eur": cost,
                "pickup_date": order.get("ship_date", ""),
                "delivery_date": order.get("delivery_date", ""),
                "carrier": "DHL Supply Chain Italy",
                "status": "scheduled",
            }
        )

    logistics_plan = {
        "total_shipments": len(shipments),
        "total_logistics_cost_eur": round(total_logistics_cost, 2),
        "shipments": shipments,
        "critical_path_days": max_lead_days,
        "bottleneck": (
            f"{bottleneck_product} — {max_lead_days} day lead time from {bottleneck_supplier}"
            if max_lead_days > 0
            else "None"
        ),
    }

    return logistics_plan, max_lead_days
