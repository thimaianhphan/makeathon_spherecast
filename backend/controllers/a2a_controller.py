"""A2A controller — Google Agent-to-Agent protocol endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.adapters.a2a_adapter import (
    generate_agent_card,
    create_task_from_message,
    process_task,
    get_task_store,
)
from backend.schemas import A2AMessage, A2APart
from backend.services.registry_service import registry

router = APIRouter(prefix="/a2a", tags=["A2A"])


@router.get("/{agent_id}/agent-card")
async def get_agent_card(agent_id: str):
    """GET /a2a/{agent_id}/agent-card — return A2A agent card."""
    agent = registry.get(agent_id)
    if not agent:
        return JSONResponse(
            content={"error": f"Agent not found: {agent_id}"},
            status_code=404,
        )
    card = generate_agent_card(agent)
    return JSONResponse(content=card.model_dump(), status_code=200)


@router.post("/{agent_id}")
async def a2a_endpoint(agent_id: str, request: Request):
    """Handle JSON-RPC 2.0 requests for A2A protocol."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
            status_code=200,
        )

    # Validate JSON-RPC version
    if body.get("jsonrpc") != "2.0":
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32600, "message": "Invalid JSON-RPC version"},
            },
            status_code=200,
        )

    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params", {})

    # Look up agent
    agent = registry.get(agent_id)
    if not agent:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32001, "message": f"Agent not found: {agent_id}"},
            },
            status_code=200,
        )

    # Dispatch by method
    if method == "tasks/send":
        if not params or "message" not in params:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing message in params"},
                },
                status_code=200,
            )
        # Create task from message
        task = create_task_from_message(agent, params)
        # Extract message and process
        msg_data = params.get("message", {})
        parts = [A2APart(**p) for p in msg_data.get("parts", [{"type": "text", "text": ""}])]
        user_msg = A2AMessage(role=msg_data.get("role", "user"), parts=parts)
        task = process_task(agent, task, user_msg)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": task.model_dump(),
            },
            status_code=200,
        )

    if method == "tasks/get":
        task_id = params.get("id")
        if not task_id:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32602, "message": "Missing task id"},
                },
                status_code=200,
            )
        task_store = get_task_store()
        if task_id not in task_store:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32002, "message": f"Task not found: {task_id}"},
                },
                status_code=200,
            )
        task = task_store[task_id]
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": task.model_dump(),
            },
            status_code=200,
        )

    # Unknown method
    return JSONResponse(
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        },
        status_code=200,
    )
