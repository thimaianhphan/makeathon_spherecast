from __future__ import annotations

from backend.schemas import (
    AgentFact,
    Capabilities,
    Certification,
    Compliance,
    ESGRating,
    Identity,
    Location,
    LocationInfo,
    NetworkInfo,
    Trust,
)


def compliance_agents() -> list[AgentFact]:
    """EU CPG food regulation compliance agents."""
    agents: list[AgentFact] = []

    # The EU Compliance Validator is defined in core.py; avoid duplication here.
    # This module can be extended with additional specialised compliance agents.

    return agents
