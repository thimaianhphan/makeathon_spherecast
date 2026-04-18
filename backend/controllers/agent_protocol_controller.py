from __future__ import annotations

from fastapi import APIRouter

from backend.schemas import AgentProtocolMessage, AgentProtocolReceipt, make_id
from backend.services.agent_transport import verify_signature

router = APIRouter()


@router.post("/agent/{agent_id}")
async def receive_agent_message(agent_id: str, msg: AgentProtocolMessage):
    if msg.to_agent and msg.to_agent != agent_id:
        return AgentProtocolReceipt(
            receipt_id=make_id("apr"),
            message_id=msg.message_id,
            from_agent=msg.from_agent,
            to_agent=agent_id,
            status="rejected",
            detail="Recipient mismatch",
        )

    signature_error = verify_signature(msg)
    if signature_error:
        return AgentProtocolReceipt(
            receipt_id=make_id("apr"),
            message_id=msg.message_id,
            from_agent=msg.from_agent,
            to_agent=agent_id,
            status="rejected",
            detail=signature_error,
        )

    return AgentProtocolReceipt(
        receipt_id=make_id("apr"),
        message_id=msg.message_id,
        from_agent=msg.from_agent,
        to_agent=agent_id,
        status="accepted",
        detail="Message received",
    )
