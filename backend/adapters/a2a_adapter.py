"""A2A adapter — Google Agent-to-Agent protocol with agent cards and task lifecycle."""

from __future__ import annotations

import asyncio
import requests
from datetime import datetime
from typing import Any

from backend.schemas import (
    A2AAgentCapabilities,
    A2AAgentCard,
    A2AAgentSkill,
    A2AArtifact,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskSendParams,
    A2ATaskStatus,
    AgentFact,
    AgentProtocolMessage,
    AgentProtocolReceipt,
    LiveMessage,
    make_id,
)
from backend.services.registry_service import registry


# ── In-memory task store ─────────────────────────────────────────────────────

_task_store: dict[str, A2ATask] = {}


def get_task_store() -> dict[str, A2ATask]:
    return _task_store


def clear_task_store() -> None:
    _task_store.clear()


# ── Agent card generation ────────────────────────────────────────────────────

def generate_agent_card(agent: AgentFact) -> A2AAgentCard:
    """Build an A2A agent card from an AgentFact."""
    msg_types = agent.network.supported_message_types if agent.network else []
    skills = [
        A2AAgentSkill(
            id=mt,
            name=mt.replace("_", " ").title(),
            description=f"Handle '{mt}' messages for {agent.name}",
            tags=[agent.role, mt],
            examples=[f"Send a {mt} to {agent.name}"],
        )
        for mt in msg_types
    ]
    endpoint = agent.network.endpoint if agent.network else ""
    return A2AAgentCard(
        name=agent.name,
        description=agent.description or f"{agent.name} ({agent.role})",
        url=endpoint,
        version=agent.network.api_version if agent.network else "1.0",
        capabilities=A2AAgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=True,
        ),
        skills=skills,
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
    )


# ── Task lifecycle ───────────────────────────────────────────────────────────

def create_task_from_message(agent: AgentFact, message: dict) -> A2ATask:
    """Create an A2A task from an incoming message payload."""
    task_id = message.get("id", make_id("task"))
    session_id = message.get("sessionId", make_id("session"))

    # Extract user message
    msg_data = message.get("message", {})
    parts = [A2APart(**p) for p in msg_data.get("parts", [{"type": "text", "text": ""}])]
    user_msg = A2AMessage(role=msg_data.get("role", "user"), parts=parts)

    task = A2ATask(
        id=task_id,
        sessionId=session_id,
        status=A2ATaskStatus(state="submitted"),
        history=[user_msg],
    )
    _task_store[task_id] = task
    return task


def process_task(agent: AgentFact, task: A2ATask, message: A2AMessage) -> A2ATask:
    """Process a task: submitted -> working -> completed."""
    # Transition to working
    task.status = A2ATaskStatus(state="working")

    # Generate response
    input_text = message.parts[0].text if message.parts else ""
    response_text = f"[{agent.name}] Processed: {input_text[:100]}" if input_text else f"[{agent.name}] Task completed"

    # Create agent response message
    agent_msg = A2AMessage(
        role="agent",
        parts=[A2APart(type="text", text=response_text)],
    )
    task.history.append(agent_msg)

    # Add artifact
    task.artifacts = [A2AArtifact(
        name="result",
        description=f"Result from {agent.name}",
        parts=[A2APart(type="text", text=response_text)],
    )]

    # Transition to completed
    task.status = A2ATaskStatus(
        state="completed",
        message=agent_msg,
    )

    _task_store[task.id] = task
    return task


# ── Client-side send ────────────────────────────────────────────────────────

async def send_a2a(endpoint: str, message: AgentProtocolMessage | dict, agent: AgentFact) -> AgentProtocolReceipt:
    """Send a message via A2A protocol.

    If endpoint is empty, performs local in-process delivery:
    - If agent.executor exists, invokes it with message data
    - Otherwise, creates and processes a task

    Remote delivery POSTs a JSON-RPC tasks/send to the endpoint.
    """
    if not endpoint:
        # Local in-process delivery
        try:
            # Extract message data
            msg_payload = message.get("params", {}).get("task", {}) if isinstance(message, dict) else {}
            if isinstance(message, dict) and "params" in message:
                msg_payload = message["params"].get("task", {})

            # If executor exists, invoke it
            if agent.executor:
                try:
                    executor_result = await agent.executor(msg_payload) if asyncio.iscoroutinefunction(
                        agent.executor
                    ) else agent.executor(msg_payload)
                    task_id = make_id("task")
                    lm = LiveMessage(
                        message_id=getattr(message, "message_id", task_id),
                        from_id=getattr(message, "from_agent", "a2a-local"),
                        from_label=getattr(message, "from_agent", "a2a-local"),
                        to_id=agent.agent_id,
                        to_label=agent.name,
                        type=getattr(message, "message_type", "a2a_execute"),
                        summary=str(executor_result)[:120],
                        detail=f"A2A executed via {agent.framework}",
                    )
                    registry.log_message(lm)
                    return AgentProtocolReceipt(
                        message_id=getattr(message, "message_id", task_id),
                        from_agent=getattr(message, "from_agent", "a2a-local"),
                        to_agent=agent.agent_id,
                        status="accepted",
                        detail=f"A2A task executed via {agent.framework}",
                        details=executor_result,
                        success=True,
                    )
                except Exception as exec_err:
                    return AgentProtocolReceipt(
                        message_id=getattr(message, "message_id", make_id("task")),
                        from_agent=getattr(message, "from_agent", "a2a-local"),
                        to_agent=agent.agent_id,
                        status="error",
                        detail=f"Executor error: {exec_err}",
                        success=False,
                    )

            # No executor: standard task lifecycle
            msg_obj = message if hasattr(message, "message_id") else type("Msg", (), message)()
            user_msg = A2AMessage(
                role="user",
                parts=[A2APart(
                    type="text",
                    text=str(msg_payload.get("content", "")) if isinstance(msg_payload, dict) else str(msg_payload),
                )],
            )
            task = A2ATask(
                status=A2ATaskStatus(state="submitted"),
                history=[user_msg],
            )
            _task_store[task.id] = task
            task = process_task(agent, task, user_msg)

            # Log the message
            lm = LiveMessage(
                message_id=getattr(message, "message_id", task.id),
                from_id=getattr(message, "from_agent", "a2a-local"),
                from_label=getattr(message, "from_agent", "a2a-local"),
                to_id=agent.agent_id,
                to_label=agent.name,
                type=getattr(message, "message_type", "a2a_message"),
                summary=str(msg_payload)[:120] if msg_payload else "",
                detail=f"A2A task {task.id} completed (local)",
            )
            registry.log_message(lm)

            return AgentProtocolReceipt(
                message_id=getattr(message, "message_id", task.id),
                from_agent=getattr(message, "from_agent", "a2a-local"),
                to_agent=agent.agent_id,
                status="accepted",
                detail=f"A2A task {task.id} completed (local)",
                success=True,
            )
        except Exception as e:
            return AgentProtocolReceipt(
                message_id=getattr(message, "message_id", make_id("task")),
                from_agent=getattr(message, "from_agent", "a2a-local"),
                to_agent=agent.agent_id,
                status="error",
                detail=f"A2A local delivery error: {e}",
                success=False,
            )

    # Remote delivery: POST JSON-RPC tasks/send
    try:
        msg_dict = message.model_dump() if hasattr(message, "model_dump") else message
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": make_id("rpc"),
            "method": "tasks/send",
            "params": {
                "id": make_id("task"),
                "sessionId": make_id("session"),
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": str(msg_dict.get("payload")) if msg_dict.get("payload") else ""}],
                },
            },
        }
        resp = requests.post(
            endpoint,
            json=jsonrpc_request,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if resp.ok:
            return AgentProtocolReceipt(
                message_id=msg_dict.get("message_id", make_id("task")),
                from_agent=msg_dict.get("from_agent", ""),
                to_agent=agent.agent_id,
                status="accepted",
                detail="A2A delivered (remote)",
                success=True,
            )
        return AgentProtocolReceipt(
            message_id=msg_dict.get("message_id", make_id("task")),
            from_agent=msg_dict.get("from_agent", ""),
            to_agent=agent.agent_id,
            status="rejected",
            detail=f"A2A remote HTTP {resp.status_code}",
            success=False,
        )
    except Exception as exc:
        return AgentProtocolReceipt(
            message_id=getattr(message, "message_id", make_id("task")),
            from_agent=getattr(message, "from_agent", ""),
            to_agent=agent.agent_id,
            status="error",
            detail=f"A2A send error: {exc}",
            success=False,
        )
