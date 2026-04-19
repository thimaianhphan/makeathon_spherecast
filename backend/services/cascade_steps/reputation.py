"""Cascade step: reputation ledger."""

from __future__ import annotations

from backend.services.trust_service import record_transactions


def run_reputation(final_orders: dict, emit) -> dict:
    return record_transactions(final_orders, emit)
