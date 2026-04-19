"""Integration tests for MCP HTTP controller endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.registry_service import registry
from backend.agents.mcp_agents import mcp_agents


client = TestClient(app)


def test_mcp_endpoint_tools_list():
    """Test MCP tools/list endpoint."""
    registry.clear()
    
    agents = mcp_agents()
    agent = agents[0]  # QualityAI
    registry.register(agent)
    
    response = client.post(
        f"/mcp/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    assert "tools" in data["result"]
    assert len(data["result"]["tools"]) == 3
    
    registry.clear()


def test_mcp_endpoint_tool_call():
    """Test MCP tools/call endpoint."""
    registry.clear()
    
    agents = mcp_agents()
    agent = agents[0]  # QualityAI
    registry.register(agent)
    
    response = client.post(
        f"/mcp/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "inspection_request",
                "arguments": {
                    "payload": {"batch_id": "batch-001"},
                    "from_agent": "ferrari-procurement-01",
                },
            },
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    assert "content" in data["result"]
    assert data["result"]["isError"] is False
    
    registry.clear()


def test_mcp_endpoint_missing_tool():
    """Test MCP endpoint with invalid tool name."""
    registry.clear()
    
    agents = mcp_agents()
    agent = agents[0]
    registry.register(agent)
    
    response = client.post(
        f"/mcp/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "invalid_tool",
                "arguments": {},
            },
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == -32602
    
    registry.clear()


def test_mcp_endpoint_agent_not_found():
    """Test MCP endpoint with non-existent agent."""
    response = client.post(
        "/mcp/nonexistent-agent-id",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == -32001


def test_mcp_endpoint_invalid_jsonrpc_version():
    """Test MCP endpoint with invalid JSON-RPC version."""
    registry.clear()
    
    agents = mcp_agents()
    agent = agents[0]
    registry.register(agent)
    
    response = client.post(
        f"/mcp/{agent.agent_id}",
        json={
            "jsonrpc": "1.0",  # Invalid version
            "id": 1,
            "method": "tools/list",
            "params": {},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == -32600
    
    registry.clear()
