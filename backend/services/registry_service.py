"""In-memory Agent Registry — the DNS of the supply chain agent network."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from backend.schemas import AgentFact, LiveMessage, NetworkInfo


def _get_reputation_score(agent_id: str) -> float | None:
    """Get live trust score from reputation ledger if available."""
    try:
        from backend.services.trust_service import reputation_ledger
        score = reputation_ledger.get_score(agent_id)
        return score.composite_score if score else None
    except Exception:
        return None


class AgentRegistry:
    """Lightweight in-memory registry supporting register / search / list / deregister."""

    def __init__(self):
        self._agents: dict[str, AgentFact] = {}
        self._messages: list[LiveMessage] = []
        self._subscribers: list[asyncio.Queue] = []
        self._deprecated: dict[str, str] = {}  # agent_id -> reason

    # ── Registration ─────────────────────────────────────────────────────

    def register(self, agent: AgentFact) -> AgentFact:
        agent.registered_at = datetime.utcnow().isoformat() + "Z"
        agent.last_heartbeat = agent.registered_at
        agent.status = "active"
        self._agents[agent.agent_id] = agent
        return agent

    def deregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def soft_deprecate(self, agent_id: str, reason: str) -> bool:
        """Mark agent as deprecated (excluded from search unless explicitly requested)."""
        if agent_id in self._agents or agent_id in self._deprecated:
            self._deprecated[agent_id] = reason
            return True
        return False

    def get_health_filters(self) -> dict:
        """Return active filters: min_trust, deprecated_agents, regions."""
        from backend.config import REGISTRY_MIN_TRUST
        return {
            "min_trust": REGISTRY_MIN_TRUST,
            "deprecated_agents": [
                {"agent_id": aid, "reason": reason}
                for aid, reason in self._deprecated.items()
            ],
            "regions": [],
        }

    # ── Lookup ───────────────────────────────────────────────────────────

    def get(self, agent_id: str) -> Optional[AgentFact]:
        return self._agents.get(agent_id)

    def list_all(self) -> list[AgentFact]:
        return list(self._agents.values())

    def list_protocol_agents(self) -> list[dict]:
        """Return protocol-ready metadata for discovery."""
        results = []
        for agent in self._agents.values():
            net = agent.network or NetworkInfo()
            results.append(
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "role": agent.role,
                    "status": agent.status,
                    "endpoint": net.endpoint,
                    "protocol": net.protocol,
                    "api_version": net.api_version,
                    "supported_message_types": net.supported_message_types,
                }
            )
        return results

    SUPPLIER_ROLES = frozenset({"tier_1_supplier", "tier_2_supplier", "raw_material_supplier"})

    def list_suppliers(self, role: Optional[str] = None) -> list[AgentFact]:
        """List all supplier agents (tier_1, tier_2, raw_material)."""
        results = [
            a for a in self._agents.values()
            if a.role in self.SUPPLIER_ROLES
        ]
        if role:
            results = [a for a in results if a.role == role]
        return results

    def search(
        self,
        role: Optional[str] = None,
        capability: Optional[str] = None,
        region: Optional[str] = None,
        certification: Optional[str] = None,
        min_trust: Optional[float] = None,
        include_deprecated: bool = False,
    ) -> list[AgentFact]:
        from backend.config import REGISTRY_MIN_TRUST

        results = list(self._agents.values())

        if not include_deprecated and self._deprecated:
            results = [a for a in results if a.agent_id not in self._deprecated]

        trust_threshold = min_trust if min_trust is not None else REGISTRY_MIN_TRUST
        if trust_threshold > 0:
            filtered = []
            for a in results:
                score = _get_reputation_score(a.agent_id)
                effective_score = score if score is not None else (a.trust.trust_score if a.trust else 0)
                if effective_score >= trust_threshold:
                    filtered.append(a)
            results = filtered

        if role:
            results = [a for a in results if a.role == role]

        if capability:
            results = [
                a for a in results
                if any(p.category == capability for p in a.capabilities.products)
            ]

        if region:
            results = [
                a for a in results
                if a.location and a.location.headquarters and a.location.headquarters.country
                and (
                    a.location.headquarters.country == region
                    or region in (a.location.shipping_regions if a.location else [])
                )
            ]

        if certification:
            results = [
                a for a in results
                if any(c.type == certification for c in a.certifications)
            ]

        return results

    # ── Message logging & SSE ────────────────────────────────────────────

    def log_message(self, msg: LiveMessage):
        self._messages.append(msg)
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def get_messages(self) -> list[LiveMessage]:
        return list(self._messages)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def clear(self):
        self._agents.clear()
        self._messages.clear()
        self._deprecated.clear()


# Global singleton
registry = AgentRegistry()
