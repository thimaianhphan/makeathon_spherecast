from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse

from backend.services.cascade_service import cascade_state
from backend.services.registry_service import registry

router = APIRouter()


# ── SSE Stream ───────────────────────────────────────────────────────────────

@router.get("/api/stream")
async def stream_messages():
    queue = registry.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    data = msg.model_dump()
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            registry.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/report")
async def get_report():
    if cascade_state["report"]:
        return cascade_state["report"]
    return JSONResponse(status_code=404, content={"error": "No report available yet"})


@router.get("/api/progress")
async def get_progress():
    return {
        "running": cascade_state["running"],
        "progress": cascade_state["progress"],
    }
