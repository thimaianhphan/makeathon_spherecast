"""Economic Memory — agents remember past interactions."""

from __future__ import annotations

from datetime import datetime

from backend.schemas import InteractionRecord, make_id


class MemoryService:
    """In-memory store of agent interaction history."""

    def __init__(self):
        self._records: list[InteractionRecord] = []

    def record_interaction(self, agent_id: str, event_type: str, payload: dict | None = None) -> InteractionRecord:
        """Record an interaction with an agent."""
        record = InteractionRecord(
            agent_id=agent_id,
            event_type=event_type,
            payload=payload or {},
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        self._records.append(record)
        return record

    def get_history(self, agent_id: str) -> list[InteractionRecord]:
        """Get interaction history for an agent."""
        return [r for r in self._records if r.agent_id == agent_id]

    def get_behavioral_signal(self, agent_id: str) -> str:
        """Get a summary behavioral signal (e.g. price_increase_after_first_order)."""
        history = self.get_history(agent_id)
        if not history:
            return ""
        event_types = [r.event_type for r in history]
        if "price_increase_post_order" in event_types:
            return "price_increase_after_first_order"
        if "delivery_late" in event_types:
            return "past_delivery_late"
        if "final_price" in event_types and len(history) > 1:
            prices = [r.payload.get("price", 0) for r in history if r.payload.get("price")]
            if len(prices) >= 2 and prices[-1] > prices[0]:
                return "price_increase_over_time"
        return ""

    def clear(self):
        """Clear all records (e.g. on cascade reset)."""
        self._records.clear()


memory_service = MemoryService()
