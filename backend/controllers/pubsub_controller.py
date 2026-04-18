from __future__ import annotations

from fastapi import APIRouter

from backend.services.pubsub_service import event_bus

router = APIRouter()


# ── Pub-Sub Endpoints ────────────────────────────────────────────────────────

@router.get("/api/pubsub/summary")
async def pubsub_summary():
    return event_bus.get_summary()


@router.get("/api/pubsub/events")
async def pubsub_events():
    return [e.model_dump() for e in event_bus.get_events()]


@router.get("/api/pubsub/subscriptions")
async def pubsub_subscriptions():
    return [s.model_dump() for s in event_bus.list_subscriptions()]
