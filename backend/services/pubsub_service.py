"""
Structured Event Broadcast Layer (Pub-Sub)

Agents subscribe to disruption categories relevant to their supply graph position.
Events are typed, categorized, and routed only to relevant subscribers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from backend.schemas import make_id


# ── Disruption Categories ────────────────────────────────────────────────────

class DisruptionCategory(str, Enum):
    MATERIAL_SHORTAGE = "material_shortage"
    LOGISTICS_DELAY = "logistics_delay"
    REGULATORY_CHANGE = "regulatory_change"
    QUALITY_RECALL = "quality_recall"
    PRICE_VOLATILITY = "price_volatility"
    PRODUCTION_HALT = "production_halt"
    GEOPOLITICAL = "geopolitical"
    WEATHER_DISRUPTION = "weather_disruption"
    LABOR_DISPUTE = "labor_dispute"
    CYBER_INCIDENT = "cyber_incident"
    PORT_CONGESTION = "port_congestion"
    CAPACITY_CONSTRAINT = "capacity_constraint"


# ── Event Schema ─────────────────────────────────────────────────────────────

class SupplyChainEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: make_id("evt"))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    category: DisruptionCategory
    severity: str = "medium"  # low, medium, high, critical
    title: str = ""
    description: str = ""
    source: str = ""  # which agent or intelligence feed produced this
    affected_regions: list[str] = Field(default_factory=list)
    affected_categories: list[str] = Field(default_factory=list)  # product categories affected
    affected_agents: list[str] = Field(default_factory=list)
    impact_assessment: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)  # arbitrary payload (prices, coordinates, etc.)
    acknowledged_by: list[str] = Field(default_factory=list)
    resolved: bool = False


# ── Subscription ─────────────────────────────────────────────────────────────

class Subscription(BaseModel):
    agent_id: str
    agent_name: str
    categories: list[DisruptionCategory]
    regions: list[str] = Field(default_factory=list)  # geographic filter
    product_categories: list[str] = Field(default_factory=list)  # product category filter
    subscribed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ── Role-based default subscriptions ─────────────────────────────────────────

ROLE_DEFAULT_SUBSCRIPTIONS: dict[str, list[DisruptionCategory]] = {
    "procurement_agent": [
        DisruptionCategory.MATERIAL_SHORTAGE,
        DisruptionCategory.PRICE_VOLATILITY,
        DisruptionCategory.PRODUCTION_HALT,
        DisruptionCategory.GEOPOLITICAL,
        DisruptionCategory.QUALITY_RECALL,
        DisruptionCategory.CAPACITY_CONSTRAINT,
    ],
    "tier_1_supplier": [
        DisruptionCategory.MATERIAL_SHORTAGE,
        DisruptionCategory.LOGISTICS_DELAY,
        DisruptionCategory.REGULATORY_CHANGE,
        DisruptionCategory.PRICE_VOLATILITY,
        DisruptionCategory.LABOR_DISPUTE,
    ],
    "tier_2_supplier": [
        DisruptionCategory.MATERIAL_SHORTAGE,
        DisruptionCategory.PRICE_VOLATILITY,
        DisruptionCategory.GEOPOLITICAL,
    ],
    "logistics_provider": [
        DisruptionCategory.LOGISTICS_DELAY,
        DisruptionCategory.WEATHER_DISRUPTION,
        DisruptionCategory.PORT_CONGESTION,
        DisruptionCategory.GEOPOLITICAL,
        DisruptionCategory.LABOR_DISPUTE,
    ],
    "compliance_agent": [
        DisruptionCategory.REGULATORY_CHANGE,
        DisruptionCategory.QUALITY_RECALL,
        DisruptionCategory.GEOPOLITICAL,
    ],
    "assembly_coordinator": [
        DisruptionCategory.PRODUCTION_HALT,
        DisruptionCategory.LOGISTICS_DELAY,
        DisruptionCategory.QUALITY_RECALL,
        DisruptionCategory.CAPACITY_CONSTRAINT,
    ],
}


# ── Event Bus ────────────────────────────────────────────────────────────────

class EventBus:
    """Pub-sub event bus for supply chain disruption events."""

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}  # agent_id → sub
        self._events: list[SupplyChainEvent] = []
        self._delivery_log: list[dict] = []  # who received what

    def subscribe(
        self,
        agent_id: str,
        agent_name: str,
        role: str,
        regions: list[str] | None = None,
        product_categories: list[str] | None = None,
    ) -> Subscription:
        """Auto-subscribe an agent based on its role and graph position."""
        categories = ROLE_DEFAULT_SUBSCRIPTIONS.get(role, [DisruptionCategory.PRODUCTION_HALT])
        sub = Subscription(
            agent_id=agent_id,
            agent_name=agent_name,
            categories=list(categories),
            regions=regions or [],
            product_categories=product_categories or [],
        )
        self._subscriptions[agent_id] = sub
        return sub

    def get_subscription(self, agent_id: str) -> Optional[Subscription]:
        return self._subscriptions.get(agent_id)

    def list_subscriptions(self) -> list[Subscription]:
        return list(self._subscriptions.values())

    def publish(self, event: SupplyChainEvent) -> list[str]:
        """Publish an event and return list of agent_ids that received it."""
        self._events.append(event)
        recipients = []

        for agent_id, sub in self._subscriptions.items():
            if event.category not in sub.categories:
                continue

            # Geographic filter: if subscriber has region filters and event has affected regions
            if sub.regions and event.affected_regions:
                if not any(r in sub.regions for r in event.affected_regions):
                    continue

            # Product category filter
            if sub.product_categories and event.affected_categories:
                if not any(c in sub.product_categories for c in event.affected_categories):
                    continue

            recipients.append(agent_id)
            self._delivery_log.append(
                {
                    "event_id": event.event_id,
                    "agent_id": agent_id,
                    "agent_name": sub.agent_name,
                    "category": event.category.value,
                    "severity": event.severity,
                    "timestamp": event.timestamp,
                }
            )

        event.acknowledged_by = recipients
        return recipients

    def acknowledge(self, event_id: str, agent_id: str):
        for evt in self._events:
            if evt.event_id == event_id and agent_id not in evt.acknowledged_by:
                evt.acknowledged_by.append(agent_id)

    def get_events(
        self,
        category: Optional[DisruptionCategory] = None,
        severity: Optional[str] = None,
    ) -> list[SupplyChainEvent]:
        results = list(self._events)
        if category:
            results = [e for e in results if e.category == category]
        if severity:
            results = [e for e in results if e.severity == severity]
        return results

    def get_delivery_log(self) -> list[dict]:
        return list(self._delivery_log)

    def get_agent_events(self, agent_id: str) -> list[SupplyChainEvent]:
        """Get all events delivered to a specific agent."""
        delivered_ids = {d["event_id"] for d in self._delivery_log if d["agent_id"] == agent_id}
        return [e for e in self._events if e.event_id in delivered_ids]

    def get_summary(self) -> dict:
        by_category = {}
        by_severity = {}
        for e in self._events:
            by_category[e.category.value] = by_category.get(e.category.value, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        return {
            "total_events": len(self._events),
            "total_subscriptions": len(self._subscriptions),
            "total_deliveries": len(self._delivery_log),
            "by_category": by_category,
            "by_severity": by_severity,
            "subscriptions": [
                {
                    "agent_id": s.agent_id,
                    "agent_name": s.agent_name,
                    "categories": [c.value for c in s.categories],
                    "regions": s.regions,
                    "product_categories": s.product_categories,
                }
                for s in self._subscriptions.values()
            ],
        }

    def clear(self):
        self._subscriptions.clear()
        self._events.clear()
        self._delivery_log.clear()


# Global singleton
event_bus = EventBus()
