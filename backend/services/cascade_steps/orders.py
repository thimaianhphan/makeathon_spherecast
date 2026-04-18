"""Cascade step: purchase orders."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta


async def run_orders(final_orders: dict, emit, desired_delivery_days: int | None) -> tuple[float, int]:
    total_component_cost = 0
    po_count = 0
    ship_date_base = datetime.utcnow() + timedelta(days=2)

    for _, order in final_orders.items():
        agent = order["agent"]
        product = order["product"]
        qty = order["quantity"]
        price = order["final_price"]
        total = round(price * qty, 2)
        total_component_cost += total

        po_number = f"PO-FERRARI-{datetime.utcnow().strftime('%Y')}-{po_count + 1:05d}"

        emit(
            "ferrari-procurement-01",
            "Ferrari Procurement",
            agent.agent_id,
            agent.name,
            "purchase_order",
            summary=None,
            payload={
                "product_name": product.name,
                "quantity": qty,
                "unit_price_eur": price,
                "total_eur": total,
                "po_number": po_number,
            },
        )

        ship_date = ship_date_base + timedelta(days=0)
        delivery_date = ship_date + timedelta(days=product.lead_time_days)

        emit(
            agent.agent_id,
            agent.name,
            "ferrari-procurement-01",
            "Ferrari Procurement",
            "order_confirmation",
            summary=None,
            payload={
                "ship_date": ship_date.strftime("%b %d"),
                "delivery_date": delivery_date.strftime("%b %d"),
                "po_number": po_number,
                "requested_delivery_days": desired_delivery_days,
            },
        )

        order["po_number"] = po_number
        order["ship_date"] = ship_date.isoformat()
        order["delivery_date"] = delivery_date.isoformat()
        order["desired_delivery_days"] = desired_delivery_days
        po_count += 1
        await asyncio.sleep(0.1)

    return total_component_cost, po_count
