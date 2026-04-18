"""Cascade step: build execution plan, graph, dashboard, and final report."""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.services.policy_service import policy_service
from backend.services.risk_propagation_service import risk_propagation


def run_reporting(
    report: dict,
    qualified_agents: dict,
    final_orders: dict,
    total_component_cost: float,
    po_count: int,
    logistics_plan: dict,
    max_lead_days: int,
    catalogue_product,
    quantity: int,
    emit,
    ts,
):
    insurance_cost = round(total_component_cost * 0.018, 2)
    compliance_fees = round(len(qualified_agents) * 200, 2)
    total_cost = total_component_cost + logistics_plan["total_logistics_cost_eur"] + insurance_cost + compliance_fees

    now = datetime.utcnow()
    report["execution_plan"] = {
        "total_cost_eur": round(total_cost, 2),
        "cost_breakdown": {
            "components_eur": round(total_component_cost, 2),
            "logistics_eur": round(logistics_plan["total_logistics_cost_eur"], 2),
            "insurance_eur": insurance_cost,
            "compliance_fees_eur": compliance_fees,
        },
        "timeline": {
            "procurement_start": now.strftime("%Y-%m-%d"),
            "all_components_ordered": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            "first_delivery": (now + timedelta(days=8)).strftime("%Y-%m-%d"),
            "last_delivery": (now + timedelta(days=max_lead_days + 3)).strftime("%Y-%m-%d"),
            "assembly_ready": (now + timedelta(days=max_lead_days + 3)).strftime("%Y-%m-%d"),
        },
        "suppliers_engaged": len(qualified_agents),
        "purchase_orders_issued": po_count,
        "risk_assessment": {
            "overall_risk": "medium",
            "risks": [],
        },
    }

    plan_for_policy = {
        "qualified_agents": qualified_agents,
        "discovery_results": report["discovery_results"],
        "execution_plan": report["execution_plan"],
    }
    policy_result = policy_service.evaluate_policy(plan_for_policy)
    report["policy_evaluation"] = {
        "compliant": policy_result.compliant,
        "violations": policy_result.violations,
        "explanations": policy_result.explanations,
    }
    if not policy_result.compliant:
        emit(
            "policy-agent",
            "Policy Agent",
            "ferrari-procurement-01",
            "Ferrari Procurement",
            "policy_violation",
            summary=None,
            payload={
                "summary": f"Policy violations: {len(policy_result.violations)}",
                "detail": "; ".join(policy_result.explanations[:3]),
            },
        )

    if catalogue_product and quantity > 0:
        total_cost_eur = report["execution_plan"]["total_cost_eur"]
        total_revenue_eur = catalogue_product.selling_price_eur * quantity
        total_profit_eur = total_revenue_eur - total_cost_eur
        margin_pct = (total_profit_eur / total_revenue_eur * 100) if total_revenue_eur > 0 else 0.0
        report["profit_summary"] = {
            "total_revenue_eur": round(total_revenue_eur, 2),
            "total_cost_eur": round(total_cost_eur, 2),
            "total_profit_eur": round(total_profit_eur, 2),
            "profit_per_item_eur": round(total_profit_eur / quantity, 2),
            "quantity": quantity,
            "margin_pct": round(margin_pct, 2),
        }

    report["component_costs"] = [
        {
            "supplier_id": order["agent"].agent_id,
            "supplier_name": order["agent"].name,
            "product_name": order["product"].name,
            "quantity": order["quantity"],
            "unit_price_eur": round(order["final_price"], 2),
            "total_eur": round(order["final_price"] * order["quantity"], 2),
        }
        for order in final_orders.values()
    ]

    color_map = {
        "procurement_agent": "#DC143C",
        "tier_1_supplier": "#2196F3",
        "tier_2_supplier": "#64B5F6",
        "raw_material_supplier": "#90CAF9",
        "contract_manufacturer": "#4CAF50",
        "logistics_provider": "#9C27B0",
        "compliance_agent": "#FF9800",
        "assembly_coordinator": "#F44336",
    }

    nodes = []
    edges = []
    node_ids_added = set()

    nodes.append(
        {
            "id": "ferrari-procurement-01",
            "label": "Ferrari Procurement",
            "role": "procurement_agent",
            "color": "#DC143C",
            "location": {"lat": 44.5294, "lon": 10.8633, "city": "Maranello"},
            "trust_score": None,
            "status": "active",
            "size": 45,
        }
    )
    node_ids_added.add("ferrari-procurement-01")

    for _, order in final_orders.items():
        agent = order["agent"]
        if agent.agent_id not in node_ids_added:
            loc = None
            if agent.location and agent.location.headquarters:
                hq = agent.location.headquarters
                loc = {"lat": hq.lat, "lon": hq.lon, "city": hq.city}
            nodes.append(
                {
                    "id": agent.agent_id,
                    "label": agent.name,
                    "role": agent.role,
                    "color": color_map.get(agent.role, "#2196F3"),
                    "location": loc,
                    "trust_score": agent.trust.trust_score if agent.trust else None,
                    "status": "active",
                    "size": 30,
                }
            )
            node_ids_added.add(agent.agent_id)

        edges.append(
            {
                "from": "ferrari-procurement-01",
                "to": agent.agent_id,
                "type": "procurement",
                "label": order.get("po_number", ""),
                "value_eur": round(order["final_price"] * order["quantity"], 2),
                "message_count": 6,
                "status": "confirmed",
            }
        )

    if "dhl-logistics-01" not in node_ids_added:
        nodes.append(
            {
                "id": "dhl-logistics-01",
                "label": "DHL Supply Chain",
                "role": "logistics_provider",
                "color": "#9C27B0",
                "location": {"lat": 45.4654, "lon": 9.1859, "city": "Milan"},
                "trust_score": 0.92,
                "status": "active",
                "size": 28,
            }
        )
        node_ids_added.add("dhl-logistics-01")

    for _, order in final_orders.items():
        agent = order["agent"]
        if agent.trust and agent.trust.ferrari_tier_status != "internal":
            edges.append(
                {
                    "from": agent.agent_id,
                    "to": "dhl-logistics-01",
                    "type": "logistics",
                    "label": "SHIP",
                    "message_count": 2,
                    "status": "scheduled",
                }
            )

    if "eu-compliance-agent-01" not in node_ids_added:
        nodes.append(
            {
                "id": "eu-compliance-agent-01",
                "label": "EU Compliance Validator",
                "role": "compliance_agent",
                "color": "#FF9800",
                "location": {"lat": 50.1109, "lon": 8.6821, "city": "Frankfurt"},
                "trust_score": 0.95,
                "status": "active",
                "size": 25,
            }
        )
        node_ids_added.add("eu-compliance-agent-01")

    edges.append(
        {
            "from": "ferrari-procurement-01",
            "to": "eu-compliance-agent-01",
            "type": "compliance",
            "label": "Validation",
            "message_count": len(qualified_agents) * 2,
            "status": "completed",
        }
    )

    if "maranello-assembly-01" not in node_ids_added:
        nodes.append(
            {
                "id": "maranello-assembly-01",
                "label": "Maranello Assembly",
                "role": "assembly_coordinator",
                "color": "#F44336",
                "location": {"lat": 44.5294, "lon": 10.8633, "city": "Maranello"},
                "trust_score": 1.0,
                "status": "active",
                "size": 25,
            }
        )

    edges.append(
        {
            "from": "ferrari-procurement-01",
            "to": "maranello-assembly-01",
            "type": "coordination",
            "label": "Assembly scheduling",
            "message_count": 2,
            "status": "confirmed",
        }
    )

    risk_propagation.report_risk("brembo-brake-supplier-01", "production_halt", 0.6)
    risk_propagation.report_risk("dhl-logistics-01", "port_delay", 0.3)
    node_risks, edge_risks = risk_propagation.propagate_risk(nodes, edges)
    for n in nodes:
        n["risk_score"] = round(node_risks.get(n["id"], 0), 2)
    for e in edges:
        src, tgt = e.get("from") or e.get("source"), e.get("to") or e.get("target")
        key = f"{src}->{tgt}"
        e["risk_level"] = round(edge_risks.get(key, 0), 2)

    report["graph_nodes"] = nodes
    report["graph_edges"] = edges

    report["dashboard"] = {
        "hero_metrics": [
            {"label": "Total Cost", "value": f"EUR {total_cost:,.0f}", "trend": None},
            {"label": "Suppliers Engaged", "value": str(len(qualified_agents)), "trend": None},
            {"label": "Time to Assembly-Ready", "value": f"{max_lead_days + 3} days", "trend": None},
        ],
        "cost_breakdown": [
            {"label": "Components", "value": round(total_component_cost, 2), "color": "#2196F3"},
            {"label": "Logistics", "value": round(logistics_plan["total_logistics_cost_eur"], 2), "color": "#9C27B0"},
            {"label": "Insurance", "value": insurance_cost, "color": "#FF9800"},
            {"label": "Compliance", "value": compliance_fees, "color": "#4CAF50"},
        ],
        "timeline_items": [],
        "supplier_markers": [],
        "supplier_routes": [],
        "risk_items": report["execution_plan"]["risk_assessment"]["risks"],
    }

    report["completed_at"] = ts()
    report["status"] = "completed"
