"""MCP controller — JSON-RPC 2.0 endpoint for Model Context Protocol."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.adapters.mcp_adapter import (
    build_error_response,
    build_tool_call_response,
    build_tools_list_response,
)
from backend.services.registry_service import registry

router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.post("/{agent_id}")
async def mcp_endpoint(agent_id: str, request: Request):
    """Handle JSON-RPC 2.0 requests for MCP protocol."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content=build_error_response(None, -32700, "Parse error"),
            status_code=200,
        )

    # Validate JSON-RPC version
    if body.get("jsonrpc") != "2.0":
        return JSONResponse(
            content=build_error_response(body.get("id"), -32600, "Invalid JSON-RPC version"),
            status_code=200,
        )

    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params", {})

    # Look up agent
    agent = registry.get(agent_id)
    if not agent:
        return JSONResponse(
            content=build_error_response(request_id, -32001, f"Agent not found: {agent_id}"),
            status_code=200,
        )

    # Dispatch by method
    if method == "tools/list":
        return JSONResponse(
            content=build_tools_list_response(agent, request_id),
            status_code=200,
        )

    if method == "tools/call":
        if not params or "name" not in params:
            return JSONResponse(
                content=build_error_response(request_id, -32602, "Missing tool name in params"),
                status_code=200,
            )
        from_agent = params.get("arguments", {}).get("from_agent", "")
        response, _receipt = build_tool_call_response(agent, request_id, params, from_agent)
        return JSONResponse(content=response, status_code=200)

    # Unknown method
    return JSONResponse(
        content=build_error_response(request_id, -32601, f"Method not found: {method}"),
        status_code=200,
    )
