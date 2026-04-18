"""Risk Propagation — risks propagate through supply graph."""

from __future__ import annotations

from datetime import datetime


class RiskPropagationService:
    """Propagate risks through supply graph edges."""

    RISK_TYPES = frozenset({"port_delay", "inventory_shortage", "price_shock", "production_halt"})

    def __init__(self):
        self._reports: list[dict] = []

    def report_risk(self, agent_id: str, risk_type: str, severity: float) -> dict:
        """Report a risk from an agent."""
        record = {
            "agent_id": agent_id,
            "risk_type": risk_type,
            "severity": min(1.0, max(0.0, severity)),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._reports.append(record)
        return record

    def propagate_risk(self, nodes: list[dict], edges: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
        """Propagate risk through graph; return node_risks, edge_risks."""
        node_risks: dict[str, float] = {}
        edge_risks: dict[str, float] = {}

        by_agent = {}
        for r in self._reports:
            aid = r["agent_id"]
            by_agent[aid] = max(by_agent.get(aid, 0), r["severity"])

        for n in nodes:
            nid = n.get("id", "")
            node_risks[nid] = by_agent.get(nid, 0.0)

        for e in edges:
            src = e.get("from") or e.get("source")
            tgt = e.get("to") or e.get("target")
            key = f"{src}->{tgt}"
            up_risk = node_risks.get(src, 0)
            edge_risks[key] = up_risk * 0.8
            if tgt and up_risk > 0:
                node_risks[tgt] = max(node_risks.get(tgt, 0), up_risk * 0.5)

        return node_risks, edge_risks

    def get_node_risks(self) -> dict[str, float]:
        """Get current node risks from reports."""
        by_agent: dict[str, float] = {}
        for r in self._reports:
            aid = r["agent_id"]
            by_agent[aid] = max(by_agent.get(aid, 0), r["severity"])
        return by_agent

    def clear(self):
        self._reports.clear()


risk_propagation = RiskPropagationService()
