"""Integration tests for A2A HTTP controller endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.registry_service import registry
from backend.agents.a2a_agents import a2a_agents
from backend.adapters.a2a_adapter import clear_task_store


client = TestClient(app)


def test_a2a_endpoint_agent_card():
    """Test A2A agent-card endpoint."""
    registry.clear()
    
    agents = a2a_agents()
    agent = agents[0]  # LogistiX
    registry.register(agent)
    
    response = client.get(f"/a2a/{agent.agent_id}/agent-card")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == agent.name
    assert data["url"] == agent.network.endpoint
    assert "capabilities" in data
    assert "skills" in data
    assert len(data["skills"]) == 3
    
    registry.clear()


def test_a2a_endpoint_agent_card_not_found():
    """Test A2A agent-card endpoint with non-existent agent."""
    response = client.get("/a2a/nonexistent-agent/agent-card")
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data


def test_a2a_endpoint_tasks_send():
    """Test A2A tasks/send endpoint."""
    clear_task_store()
    registry.clear()
    
    agents = a2a_agents()
    agent = agents[0]  # LogistiX
    registry.register(agent)
    
    response = client.post(
        f"/a2a/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "id": "task-001",
                "sessionId": "session-001",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Optimize route to Milan"}],
                },
            },
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    
    # Check task structure
    task = data["result"]
    assert task["id"] == "task-001"
    assert task["status"]["state"] == "completed"
    assert len(task["history"]) == 2  # User message + agent response
    assert len(task["artifacts"]) > 0
    
    clear_task_store()
    registry.clear()


def test_a2a_endpoint_tasks_get():
    """Test A2A tasks/get endpoint."""
    clear_task_store()
    registry.clear()
    
    agents = a2a_agents()
    agent = agents[0]
    registry.register(agent)
    
    # First, create a task
    client.post(
        f"/a2a/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "id": "task-retrieve",
                "sessionId": "session-001",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Get route"}],
                },
            },
        },
    )
    
    # Then, retrieve it
    response = client.post(
        f"/a2a/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tasks/get",
            "params": {"id": "task-retrieve"},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 2
    assert "result" in data
    assert data["result"]["id"] == "task-retrieve"
    assert data["result"]["status"]["state"] == "completed"
    
    clear_task_store()
    registry.clear()


def test_a2a_endpoint_tasks_get_not_found():
    """Test A2A tasks/get endpoint with non-existent task."""
    registry.clear()
    
    agents = a2a_agents()
    agent = agents[0]
    registry.register(agent)
    
    response = client.post(
        f"/a2a/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {"id": "nonexistent-task"},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == -32002
    
    registry.clear()


def test_a2a_endpoint_invalid_method():
    """Test A2A endpoint with invalid method."""
    registry.clear()
    
    agents = a2a_agents()
    agent = agents[0]
    registry.register(agent)
    
    response = client.post(
        f"/a2a/{agent.agent_id}",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "invalid_method",
            "params": {},
        },
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "error" in data
    assert data["error"]["code"] == -32601
    
    registry.clear()
