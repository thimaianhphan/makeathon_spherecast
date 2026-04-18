"""MCP adapter — JSON-RPC 2.0 client/server for Model Context Protocol."""

from __future__ import annotations

import asyncio
import requests
from typing import Any

from backend.schemas import (
    AgentFact,
    AgentProtocolMessage,
    AgentProtocolReceipt,
    LiveMessage,
    McpToolCallParams,
    McpToolCallResult,
    McpToolDefinition,
    McpToolsListResult,
    make_id,
)
from backend.services.registry_service import registry


# ── Tool derivation ──────────────────────────────────────────────────────────

def agent_tools_from_fact(agent: AgentFact) -> list[McpToolDefinition]:
    """Derive MCP tool definitions from an agent's supported_message_types."""
    tools: list[McpToolDefinition] = []
    msg_types = agent.network.supported_message_types if agent.network else []
    for mt in msg_types:
        tools.append(McpToolDefinition(
            name=mt,
            description=f"Send a '{mt}' message to {agent.name}",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "object", "description": "Message payload"},
                    "from_agent": {"type": "string", "description": "Sender agent ID"},
                },
                "required": ["payload"],
            },
        ))
    return tools


# ── JSON-RPC response builders ───────────────────────────────────────────────

def build_tools_list_response(agent: AgentFact, request_id: Any) -> dict:
    """Build a JSON-RPC 2.0 response for tools/list."""
    tools = agent_tools_from_fact(agent)
    result = McpToolsListResult(tools=tools)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result.model_dump(),
    }


def build_tool_call_response(
    agent: AgentFact,
    request_id: Any,
    params: dict,
    from_agent: str = "",
) -> tuple[dict, AgentProtocolReceipt]:
    """Handle tools/call: execute the tool and return JSON-RPC response + receipt."""
    tool_params = McpToolCallParams(**params)

    # Verify tool exists
    available = {t.name for t in agent_tools_from_fact(agent)}
    if tool_params.name not in available:
        return build_error_response(request_id, -32602, f"Unknown tool: {tool_params.name}"), AgentProtocolReceipt(
            status="rejected", detail=f"Unknown tool: {tool_params.name}",
        )

    # Log the message via registry
    msg_id = make_id("mcp")
    lm = LiveMessage(
        message_id=msg_id,
        from_id=from_agent or "mcp-client",
        from_label=from_agent or "mcp-client",
        to_id=agent.agent_id,
        to_label=agent.name,
        type=tool_params.name,
        summary=str(tool_params.arguments)[:120] if tool_params.arguments else "",
        detail=f"MCP tools/call: {tool_params.name}",
    )
    registry.log_message(lm)

    # Build result
    tool_result = McpToolCallResult(
        content=[{"type": "text", "text": f"Tool '{tool_params.name}' executed on {agent.name}"}],
        isError=False,
    )
    receipt = AgentProtocolReceipt(
        message_id=msg_id,
        from_agent=from_agent,
        to_agent=agent.agent_id,
        status="accepted",
        detail=f"MCP tool call: {tool_params.name}",
    )

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": tool_result.model_dump(),
    }, receipt


def build_error_response(request_id: Any, code: int, message: str) -> dict:
    """Build a JSON-RPC 2.0 error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


# ── Client-side send ────────────────────────────────────────────────────────

async def send_mcp(endpoint: str, message: AgentProtocolMessage | dict, agent: AgentFact) -> AgentProtocolReceipt:
    """Send a message via MCP protocol.

    If endpoint is empty, performs local in-process delivery:
    - If agent.executor exists, invokes the executor with message data
    - Otherwise, logs and returns accepted

    Remote delivery POSTs a JSON-RPC tools/call to the endpoint.
    """
    if not endpoint:
        # Local in-process delivery
        try:
            # Extract message data
            msg_payload = message.get("params", {}).get("task", {})
            if isinstance(message, dict) and "params" in message:
                msg_payload = message["params"].get("input", {}) or message["params"].get("task", {})

            # If executor exists, invoke it
            if agent.executor:
                try:
                    executor_result = await agent.executor(msg_payload) if asyncio.iscoroutinefunction(
                        agent.executor
                    ) else agent.executor(msg_payload)
                    lm = LiveMessage(
                        message_id=getattr(message, "message_id", make_id("mcp")),
                        from_id=getattr(message, "from_agent", "mcp-local"),
                        from_label=getattr(message, "from_agent", "mcp-local"),
                        to_id=agent.agent_id,
                        to_label=agent.name,
                        type=getattr(message, "message_type", "mcp_execute"),
                        summary=str(executor_result)[:120],
                        detail=f"MCP executed via {agent.framework}",
                    )
                    registry.log_message(lm)
                    return AgentProtocolReceipt(
                        message_id=getattr(message, "message_id", make_id("mcp")),
                        from_agent=getattr(message, "from_agent", "mcp-local"),
                        to_agent=agent.agent_id,
                        status="accepted",
                        detail=f"Executed via {agent.framework}",
                        details=executor_result,
                        success=True,
                    )
                except Exception as exec_err:
                    return AgentProtocolReceipt(
                        message_id=getattr(message, "message_id", make_id("mcp")),
                        from_agent=getattr(message, "from_agent", "mcp-local"),
                        to_agent=agent.agent_id,
                        status="error",
                        detail=f"Executor error: {exec_err}",
                        success=False,
                    )

            # No executor: just log
            lm = LiveMessage(
                message_id=getattr(message, "message_id", make_id("mcp")),
                from_id=getattr(message, "from_agent", "mcp-local"),
                from_label=getattr(message, "from_agent", "mcp-local"),
                to_id=agent.agent_id,
                to_label=agent.name,
                type=getattr(message, "message_type", "mcp_message"),
                summary=str(msg_payload)[:120] if msg_payload else "",
                detail="Delivered via MCP (local)",
            )
            registry.log_message(lm)
            return AgentProtocolReceipt(
                message_id=getattr(message, "message_id", make_id("mcp")),
                from_agent=getattr(message, "from_agent", "mcp-local"),
                to_agent=agent.agent_id,
                status="accepted",
                detail="Delivered via MCP (local)",
                success=True,
            )
        except Exception as e:
            return AgentProtocolReceipt(
                message_id=getattr(message, "message_id", make_id("mcp")),
                from_agent=getattr(message, "from_agent", "mcp-local"),
                to_agent=agent.agent_id,
                status="error",
                detail=f"MCP local delivery error: {e}",
                success=False,
            )

    # Remote delivery: POST JSON-RPC tools/call
    try:
        msg_dict = message.model_dump() if hasattr(message, "model_dump") else message
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": make_id("rpc"),
            "method": "tools/call",
            "params": {
                "name": msg_dict.get("message_type") or "message",
                "arguments": {
                    "payload": msg_dict.get("payload"),
                    "from_agent": msg_dict.get("from_agent"),
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
                message_id=msg_dict.get("message_id", make_id("mcp")),
                from_agent=msg_dict.get("from_agent", ""),
                to_agent=agent.agent_id,
                status="accepted",
                detail="Delivered via MCP (remote)",
                success=True,
            )
        return AgentProtocolReceipt(
            message_id=msg_dict.get("message_id", make_id("mcp")),
            from_agent=msg_dict.get("from_agent", ""),
            to_agent=agent.agent_id,
            status="rejected",
            detail=f"MCP remote HTTP {resp.status_code}",
            success=False,
        )
    except Exception as exc:
        return AgentProtocolReceipt(
            message_id=getattr(message, "message_id", make_id("mcp")),
            from_agent=getattr(message, "from_agent", ""),
            to_agent=agent.agent_id,
            status="error",
            detail=f"MCP send error: {exc}",
            success=False,
        )
