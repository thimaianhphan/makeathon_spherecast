"""
Network-Wide Intelligence Feed

Aggregates real-world signals and pushes typed events into the agent network.
"""

from __future__ import annotations

import asyncio
import random

from backend.services.pubsub_service import DisruptionCategory, SupplyChainEvent
from backend.schemas import LiveMessage, make_id
from backend.services.agent_service import ai_reason
from backend.services.registry_service import registry


# ── Intelligence Signal Templates ────────────────────────────────────────────

SIGNAL_TEMPLATES = [
    {
        "category": DisruptionCategory.WEATHER_DISRUPTION,
        "severity": "high",
        "title": "Severe Storm System — Northern Italy / Alpine Passes",
        "description": "Heavy snowfall and ice expected across Brenner Pass and A22 motorway for 48-72 hours. Road freight delays of 12-24 hours anticipated for trans-Alpine routes.",
        "affected_regions": ["IT", "AT", "DE"],
        "affected_categories": ["body_chassis", "braking_system", "suspension"],
        "source": "EUMETSAT / National Weather Service",
        "recommended_actions": [
            "Reroute shipments via coastal A1 corridor",
            "Pre-position inventory at Milan hub",
            "Alert suppliers north of Alps to ship 24h early",
        ],
        "data": {"wind_speed_kmh": 95, "snowfall_cm": 45, "duration_hours": 72,
                 "affected_routes": ["A22 Brenner", "A13 Inntal", "SS12 del Brennero"]},
    },
    {
        "category": DisruptionCategory.REGULATORY_CHANGE,
        "severity": "medium",
        "title": "EU REACH Regulation Amendment — New SVHC Substances Added",
        "description": "European Chemicals Agency (ECHA) added 4 new Substances of Very High Concern to the REACH candidate list, effective in 90 days. Affects chrome-plating processes and certain flame retardants used in automotive interior materials.",
        "affected_regions": ["EU"],
        "affected_categories": ["interior", "electronics"],
        "source": "ECHA Regulatory Database",
        "recommended_actions": [
            "Audit all Tier 1 suppliers for SVHC exposure",
            "Request material declarations from interior suppliers",
            "Evaluate alternative flame retardant compounds",
            "Update compliance check thresholds",
        ],
        "data": {"regulation": "EU REACH", "substances_added": 4,
                 "effective_in_days": 90, "reference": "ECHA/2025/C-041"},
    },
    {
        "category": DisruptionCategory.PRICE_VOLATILITY,
        "severity": "high",
        "title": "Carbon Fiber Spot Price Surge — +18% Week-over-Week",
        "description": "Global carbon fiber prices spiked 18% due to production curtailments at major Japanese producers (Toray, Teijin). PAN precursor shortage driving upstream cost pressure. Affects all carbon-ceramic and carbon-composite components.",
        "affected_regions": ["EU", "JP", "NA"],
        "affected_categories": ["braking_system", "body_chassis", "exhaust_emissions"],
        "source": "Composites Market Intelligence / Bloomberg Commodities",
        "recommended_actions": [
            "Lock in forward contracts with current suppliers",
            "Evaluate inventory buffers for carbon-based components",
            "Assess alternative materials for non-critical applications",
            "Negotiate price adjustment caps with Tier 1 suppliers",
        ],
        "data": {"commodity": "carbon_fiber_T800", "price_change_pct": 18.3,
                 "current_price_eur_kg": 28.50, "previous_price_eur_kg": 24.10,
                 "30d_trend": "sharply_rising"},
    },
    {
        "category": DisruptionCategory.PORT_CONGESTION,
        "severity": "medium",
        "title": "Port of Genoa — Container Backlog Exceeds 72 Hours",
        "description": "Labor action at Genoa port terminal has created a container backlog. Average dwell time now 96 hours vs normal 24 hours. Affects inbound shipments from non-EU suppliers.",
        "affected_regions": ["IT"],
        "affected_categories": ["electronics", "suspension", "wheels_tires"],
        "source": "MarineTraffic / Port Authority of Genoa",
        "recommended_actions": [
            "Divert inbound containers to La Spezia or Livorno",
            "Switch to air freight for critical time-sensitive components",
            "Extend delivery windows by 3-5 days for affected POs",
        ],
        "data": {"port": "Genoa (ITGOA)", "avg_dwell_hours": 96, "normal_dwell_hours": 24,
                 "vessels_waiting": 12, "estimated_resolution_days": 5},
    },
    {
        "category": DisruptionCategory.QUALITY_RECALL,
        "severity": "critical",
        "title": "Recall Notice — ECU Firmware Vulnerability CVE-2025-4821",
        "description": "Critical vulnerability discovered in TriCore TC397 ECU firmware affecting engine management timing. NHTSA and UNECE flagged for immediate remediation. All ECUs with firmware v3.2.x require reflash.",
        "affected_regions": ["EU", "NA", "APAC"],
        "affected_categories": ["electronics", "powertrain"],
        "source": "NHTSA Recall Database / UNECE WP.29",
        "recommended_actions": [
            "Halt shipment of affected ECU firmware versions",
            "Request firmware patch from Magneti Marelli",
            "Audit all in-transit and warehoused ECUs",
            "Update assembly line QC to verify firmware version",
        ],
        "data": {"cve": "CVE-2025-4821", "affected_firmware": "v3.2.x",
                 "affected_processor": "TriCore_TC397", "severity_cvss": 8.4,
                 "units_potentially_affected": 15000},
    },
    {
        "category": DisruptionCategory.GEOPOLITICAL,
        "severity": "medium",
        "title": "New EU Tariff Schedule — Automotive Component Surcharges",
        "description": "EU Council approved 6.5% import tariff on select automotive components from non-FTA countries, effective next quarter. Impacts suspension components from Canada (Multimatic) unless CETA exemption applies.",
        "affected_regions": ["EU", "CA", "GB"],
        "affected_categories": ["suspension"],
        "source": "EU Official Journal / DG Trade",
        "recommended_actions": [
            "Verify CETA preferential origin certificates for Multimatic",
            "Calculate tariff exposure for non-EU sourced components",
            "Evaluate EU-based alternative suppliers",
            "File for tariff exemption if applicable",
        ],
        "data": {"tariff_rate_pct": 6.5, "effective_quarter": "Q2 2025",
                 "exemption_treaties": ["CETA", "EU-JP EPA"],
                 "reference": "EU Regulation 2025/0412"},
    },
    {
        "category": DisruptionCategory.LABOR_DISPUTE,
        "severity": "medium",
        "title": "IG Metall Strike Action — German Automotive Suppliers",
        "description": "IG Metall union announced 48-hour warning strike at German automotive parts facilities. Could affect Tier 2 aluminum suppliers feeding into Italian Tier 1 manufacturers.",
        "affected_regions": ["DE"],
        "affected_categories": ["braking_system", "suspension", "wheels_tires"],
        "source": "IG Metall Press Release / Reuters",
        "recommended_actions": [
            "Assess Tier 2 exposure in German supply base",
            "Pre-order safety stock from affected suppliers",
            "Identify alternative Tier 2 sources in AT/CZ",
        ],
        "data": {"union": "IG Metall", "duration_hours": 48,
                 "facilities_affected": 23, "workers_involved": 8500},
    },
    {
        "category": DisruptionCategory.CAPACITY_CONSTRAINT,
        "severity": "high",
        "title": "Dallara Compositi — Autoclave Maintenance Shutdown",
        "description": "Dallara's primary autoclave requires unplanned maintenance (pressure vessel inspection). Production capacity reduced by 60% for 10 days. Carbon monocoque deliveries will be delayed.",
        "affected_regions": ["IT"],
        "affected_categories": ["body_chassis"],
        "source": "Supplier Direct Notification",
        "recommended_actions": [
            "Prioritize Ferrari orders in remaining capacity",
            "Evaluate if secondary autoclave can handle partial load",
            "Assess impact on assembly timeline",
            "Notify assembly coordinator of potential delay",
        ],
        "data": {"facility": "Dallara Varano de' Melegari", "equipment": "Autoclave #1",
                 "capacity_reduction_pct": 60, "duration_days": 10,
                 "affected_product": "Carbon Fiber Monocoque - 296 GTB"},
    },
]


# ── Intelligence Feed Runner ─────────────────────────────────────────────────

async def generate_intelligence_signals(event_bus, count: int = 5) -> list[dict]:
    """Generate realistic intelligence signals and push them through the event bus."""
    results = []
    selected = random.sample(SIGNAL_TEMPLATES, min(count, len(SIGNAL_TEMPLATES)))

    for template in selected:
        event = SupplyChainEvent(
            category=template["category"],
            severity=template["severity"],
            title=template["title"],
            description=template["description"],
            source=template["source"],
            affected_regions=template["affected_regions"],
            affected_categories=template["affected_categories"],
            recommended_actions=template["recommended_actions"],
            data=template["data"],
        )

        # Publish and get recipients
        recipients = event_bus.publish(event)

        # Emit to live feed
        severity_colors = {"low": "#4CAF50", "medium": "#FF9800", "high": "#F44336", "critical": "#D32F2F"}

        _emit_intel(
            event.source,
            event.category.value,
            f"INTEL: {event.title}",
            f"Severity: {event.severity.upper()} | Delivered to {len(recipients)} agents | {event.description[:120]}...",
            severity_colors.get(event.severity, "#FF9800"),
        )

        # Generate AI reaction from Ferrari Procurement
        if recipients:
            reaction = await ai_reason(
                "Ferrari Procurement AI",
                "procurement_agent",
                f"Intelligence alert received: {event.title}. {event.description} "
                f"Affected categories: {', '.join(event.affected_categories)}. "
                f"Recommended actions: {'; '.join(event.recommended_actions[:2])}. "
                f"What is your immediate response?",
            )

            _emit_intel(
                "Ferrari Procurement",
                "intel_response",
                f"Response to: {event.title[:60]}",
                reaction,
                "#DC143C",
            )

            results.append(
                {
                    "event": event.model_dump(),
                    "recipients": recipients,
                    "recipient_count": len(recipients),
                    "ai_reaction": reaction,
                }
            )

        await asyncio.sleep(0.2)

    return results


def _emit_intel(from_label, msg_type, summary, detail, color):
    msg = LiveMessage(
        message_id=make_id("intel"),
        from_id="intelligence-feed",
        from_label=from_label,
        to_id="network",
        to_label="Agent Network",
        type=f"intel_{msg_type}",
        summary=summary,
        detail=detail,
        color=color,
        icon="satellite",
    )
    registry.log_message(msg)
