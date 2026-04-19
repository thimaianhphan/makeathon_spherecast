"""Cross-protocol routing tests."""

from __future__ import annotations

from backend.schemas import AgentProtocolMessage
from backend.services.registry_service import registry
from backend.services.agent_transport import send_to_agent
from backend.agents.core import core_agents
from backend.agents.mcp_agents import mcp_agents
from backend.agents.a2a_agents import a2a_agents
from backend.adapters.a2a_adapter import clear_task_store


def test_http_to_mcp_routing():
    """Test HTTP agent sending to MCP agent."""
    registry.clear()
    
    http_agents = core_agents()
    mcp_agent_list = mcp_agents()
    
    sender = http_agents[0]  # Ferrari Procurement (HTTP)
    recipient = mcp_agent_list[0]  # QualityAI (MCP)
    
    # Clear endpoints for local delivery test
    sender.network.endpoint = ""
    recipient.network.endpoint = ""
    
    registry.register(sender)
    registry.register(recipient)
    
    msg = AgentProtocolMessage(
        from_agent=sender.agent_id,
        to_agent=recipient.agent_id,
        message_type="inspection_request",
        payload={"batch_id": "batch-001"},
    )
    
    receipt = send_to_agent(msg)
    
    assert receipt.status == "accepted"
    assert "MCP" in receipt.detail
    
    registry.clear()


def test_mcp_to_a2a_routing():
    """Test MCP agent sending to A2A agent."""
    clear_task_store()
    registry.clear()
    
    mcp_agent_list = mcp_agents()
    a2a_agent_list = a2a_agents()
    
    sender = mcp_agent_list[0]  # QualityAI (MCP)
    recipient = a2a_agent_list[0]  # LogistiX (A2A)
    
    # Clear endpoints for local delivery test
    sender.network.endpoint = ""
    recipient.network.endpoint = ""
    
    registry.register(sender)
    registry.register(recipient)
    
    msg = AgentProtocolMessage(
        from_agent=sender.agent_id,
        to_agent=recipient.agent_id,
        message_type="route_request",
        payload={"origin": "Munich", "destination": "Maranello"},
    )
    
    receipt = send_to_agent(msg)
    
    assert receipt.status == "accepted"
    assert "A2A" in receipt.detail or "task" in receipt.detail
    
    clear_task_store()
    registry.clear()


def test_a2a_to_mcp_routing():
    """Test A2A agent sending to MCP agent."""
    registry.clear()
    
    a2a_agent_list = a2a_agents()
    mcp_agent_list = mcp_agents()
    
    sender = a2a_agent_list[1]  # MarketIntel (A2A)
    recipient = mcp_agent_list[1]  # PredictMaint (MCP)
    
    # Clear endpoints for local delivery test
    sender.network.endpoint = ""
    recipient.network.endpoint = ""
    
    registry.register(sender)
    registry.register(recipient)
    
    msg = AgentProtocolMessage(
        from_agent=sender.agent_id,
        to_agent=recipient.agent_id,
        message_type="maintenance_prediction",
        payload={"asset_id": "pump-001", "usage_hours": 2500},
    )
    
    receipt = send_to_agent(msg)
    
    assert receipt.status == "accepted"
    assert "MCP" in receipt.detail
    
    registry.clear()


def test_framework_diversity():
    """Verify agents use diverse frameworks."""
    mcp_agents_list = mcp_agents()
    a2a_agents_list = a2a_agents()
    
    # MCP agents: LangChain and AutoGen
    frameworks = {a.network.framework for a in mcp_agents_list if a.network}
    assert "langchain" in frameworks
    assert "autogen" in frameworks
    
    # A2A agents: plain_python and LangChain
    frameworks = {a.network.framework for a in a2a_agents_list if a.network}
    assert "plain_python" in frameworks
    assert "langchain" in frameworks
