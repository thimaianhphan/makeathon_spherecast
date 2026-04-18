"""Agent seed data grouped by domain."""

from backend.agents.a2a_agents import a2a_agents
from backend.agents.category_map import CATEGORY_AGENT_MAP
from backend.agents.compliance import compliance_agents
from backend.agents.core import core_agents
from backend.agents.disqualified import disqualified_agents
from backend.agents.logistics import logistics_agents
from backend.agents.mcp_agents import mcp_agents
from backend.agents.suppliers import supplier_agents

__all__ = [
    "a2a_agents",
    "CATEGORY_AGENT_MAP",
    "compliance_agents",
    "core_agents",
    "disqualified_agents",
    "logistics_agents",
    "mcp_agents",
    "supplier_agents",
]
