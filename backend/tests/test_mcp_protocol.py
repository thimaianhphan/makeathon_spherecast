"""Unit tests for MCP (JSON-RPC 2.0) protocol adapter."""

from __future__ import annotations

from backend.schemas import (
    AgentFact,
    AgentProtocolMessage,
    NetworkInfo,
)
from backend.services.registry_service import registry
from backend.services.agent_transport import send_to_agent
from backend.agents.mcp_agents import mcp_agents


def test_mcp_agent_tools_derivation():
    """Test that MCP tools are correctly derived from supported_message_types."""
    from backend.adapters.mcp_adapter import agent_tools_from_fact
    
    agents = mcp_agents()
    agent = agents[0]  # QualityAI
    
    tools = agent_tools_from_fact(agent)
    
    assert len(tools) == 3
    tool_names = {t.name for t in tools}
    assert "inspection_request" in tool_names
    assert "quality_report" in tool_names
    assert "defect_alert" in tool_names
    
    # Check tool structure
    tool = tools[0]
    assert tool.description
    assert tool.inputSchema is not None
    assert "type" in tool.inputSchema
    assert "properties" in tool.inputSchema


def test_mcp_send_to_agent_local_delivery():
    """Test MCP delivery with empty endpoint (local in-process)."""
    registry.clear()
    
    # Register agents
    agents = mcp_agents()
    sender = agents[0]  # QualityAI
    recipient = agents[1]  # PredictMaint
    
    # Clear endpoints for local delivery test
    sender.network.endpoint = ""
    recipient.network.endpoint = ""
    
    registry.register(sender)
    registry.register(recipient)
    
    # Send message
    msg = AgentProtocolMessage(
        from_agent=sender.agent_id,
        to_agent=recipient.agent_id,
        message_type="inspection_request",
        payload={"defect_probability": 0.05},
    )
    
    receipt = send_to_agent(msg)
    
    # Debug: print receipt details if failed
    if receipt.status != "accepted":
        print(f"Receipt status: {receipt.status}, detail: {receipt.detail}")
    
    assert receipt.status == "accepted"
    assert receipt.message_id == msg.message_id
    assert "MCP" in receipt.detail
    
    # Verify message was logged
    messages = registry.get_messages()
    assert any(m.message_id == msg.message_id for m in messages)
    
    registry.clear()


def test_mcp_json_rpc_response_format():
    """Test that JSON-RPC responses are properly formatted."""
    from backend.adapters.mcp_adapter import build_tools_list_response, build_error_response
    
    agents = mcp_agents()
    agent = agents[0]
    
    # Test tools/list response
    response = build_tools_list_response(agent, 1)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert "tools" in response["result"]
    
    # Test error response
    error_response = build_error_response(1, -32602, "Invalid params")
    assert error_response["jsonrpc"] == "2.0"
    assert error_response["id"] == 1
    assert "error" in error_response
    assert error_response["error"]["code"] == -32602
