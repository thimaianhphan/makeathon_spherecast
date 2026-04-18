from __future__ import annotations

from backend.services.registry_service import registry
from backend.services.agent_transport import send_to_agent
from backend.schemas import AgentProtocolMessage

from backend.agents.core import core_agents
from backend.agents.suppliers import supplier_agents


def test_send_to_agent_mcp_logs_and_returns_accepted():
	# start with a clean registry
	registry.clear()
	print("\n✓ Registry cleared")

	# Use real agents from the agents folder
	core = core_agents()
	suppliers = supplier_agents()
	print(f"✓ Loaded {len(core)} core agents and {len(suppliers)} supplier agents")

	# sender: Ferrari Procurement (from core_agents)
	sender = next((a for a in core if a.agent_id == "ferrari-procurement-01"), None)
	assert sender is not None
	print(f"✓ Sender: {sender.name} ({sender.agent_id})")

	# recipient: pick a supplier (Brembo) and switch it to MCP transport for the test
	recipient = next((a for a in suppliers if a.agent_id == "brembo-brake-supplier-01"), None)
	assert recipient is not None
	recipient.network.protocol = "MCP"
	recipient.network.endpoint = ""
	print(f"✓ Recipient: {recipient.name} ({recipient.agent_id}) switched to MCP protocol")

	# register both agents in the in-memory registry
	registry.register(sender)
	registry.register(recipient)
	print(f"✓ Both agents registered in registry")

	# Build protocol message and send
	msg = AgentProtocolMessage(
		from_agent=sender.agent_id,
		to_agent=recipient.agent_id,
		message_type="test.mcp",
		payload={"hello": "mcp"},
	)
	print(f"✓ Message created: {msg.message_id}")

	receipt = send_to_agent(msg)
	print(f"✓ Receipt received: status={receipt.status}, detail={receipt.detail}")

	assert receipt is not None
	assert receipt.message_id == msg.message_id
	assert receipt.status == "accepted"
	print(f"✓ All receipt assertions passed")

	# Ensure registry recorded the live message
	messages = registry.get_messages()
	print(f"✓ Registry has {len(messages)} live message(s)")
	matching = [m for m in messages if m.message_id == msg.message_id]
	assert len(matching) > 0
	print(f"✓ Found matching MCP message in registry: {matching[0].detail}")

	# Cleanup
	registry.clear()
	print(f"✓ Registry cleared (test complete)\n")
 
if __name__ == "__main__":
    test_send_to_agent_mcp_logs_and_returns_accepted() 
