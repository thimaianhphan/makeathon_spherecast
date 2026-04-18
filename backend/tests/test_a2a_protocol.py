"""Unit tests for A2A (Agent-to-Agent) protocol adapter."""

from __future__ import annotations

from backend.schemas import (
    AgentProtocolMessage,
    A2AMessage,
    A2APart,
)
from backend.services.registry_service import registry
from backend.services.agent_transport import send_to_agent
from backend.agents.a2a_agents import a2a_agents
from backend.adapters.a2a_adapter import (
    generate_agent_card,
    clear_task_store,
    create_task_from_message,
    process_task,
    get_task_store,
)


def test_a2a_agent_card_generation():
    """Test A2A agent card generation from AgentFact."""
    agents = a2a_agents()
    agent = agents[0]  # LogistiX
    
    card = generate_agent_card(agent)
    
    assert card.name == agent.name
    assert card.url == agent.network.endpoint
    assert len(card.skills) == 3
    assert card.capabilities.stateTransitionHistory is True
    
    # Check skills are derived from message types
    skill_names = {s.name for s in card.skills}
    assert "Route Request" in skill_names
    assert "Route Result" in skill_names


def test_a2a_task_lifecycle():
    """Test A2A task creation and processing."""
    clear_task_store()
    
    agents = a2a_agents()
    agent = agents[0]  # LogistiX
    
    # Create task
    task_params = {
        "id": "task-123",
        "sessionId": "session-456",
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": "Optimize route to Milan"}],
        },
    }
    
    task = create_task_from_message(agent, task_params)
    
    assert task.id == "task-123"
    assert task.status.state == "submitted"
    assert len(task.history) == 1
    assert task.history[0].role == "user"
    
    # Process task
    user_msg = task.history[0]
    task = process_task(agent, task, user_msg)
    
    assert task.status.state == "completed"
    assert len(task.history) == 2
    assert task.history[1].role == "agent"
    assert len(task.artifacts) > 0
    
    # Verify task is stored
    store = get_task_store()
    assert task.id in store
    
    clear_task_store()


def test_a2a_send_to_agent_local_delivery():
    """Test A2A delivery with empty endpoint (local in-process)."""
    clear_task_store()
    registry.clear()
    
    agents = a2a_agents()
    sender = agents[0]  # LogistiX
    recipient = agents[1]  # MarketIntel
    
    # Clear endpoints for local delivery test
    sender.network.endpoint = ""
    recipient.network.endpoint = ""
    
    registry.register(sender)
    registry.register(recipient)
    
    # Send message
    msg = AgentProtocolMessage(
        from_agent=sender.agent_id,
        to_agent=recipient.agent_id,
        message_type="route_request",
        payload={"origin": "Turin", "destination": "Milan", "cost_limit": 500},
    )
    
    receipt = send_to_agent(msg)
    
    assert receipt.status == "accepted"
    assert "A2A" in receipt.detail
    assert "task" in receipt.detail
    
    # Verify message was logged
    messages = registry.get_messages()
    assert any(m.message_id == msg.message_id for m in messages)
    
    # Verify task was created and completed
    store = get_task_store()
    assert len(store) > 0
    
    clear_task_store()
    registry.clear()


def test_a2a_message_structure():
    """Test A2A message part structure."""
    part = A2APart(type="text", text="Route optimization request")
    assert part.type == "text"
    assert part.text == "Route optimization request"
    
    msg = A2AMessage(role="user", parts=[part])
    assert msg.role == "user"
    assert len(msg.parts) == 1
    assert msg.parts[0].text == "Route optimization request"
