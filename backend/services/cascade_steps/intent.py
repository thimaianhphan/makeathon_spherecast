"""Cascade step: intent expansion + BOM decomposition."""

from __future__ import annotations

import asyncio

from backend.services.intent_resolver_service import intent_resolver
from backend.services.agent_service import ai_reason


async def run_intent(intent: str, report: dict, emit, ts) -> list[dict]:
    emit(
        "ferrari-procurement-01",
        "Ferrari Procurement",
        "system",
        "System",
        "intent_expansion",
        summary=None,
        payload={"summary": f"Expanding intent: {intent[:80]}..."},
    )

    intent_expansion, bom = await intent_resolver.expand_and_decompose(intent)
    report["intent_expansion"] = intent_expansion
    emit(
        "intent-resolver",
        "Intent Resolver",
        "ferrari-procurement-01",
        "Ferrari Procurement",
        "intent_expansion",
        summary=None,
        payload={"summary": "Intent expanded", "detail": str(intent_expansion)},
    )

    reasoning = await ai_reason(
        "Ferrari Procurement AI",
        "procurement_agent",
        f"You received the intent: '{intent}'. Explain your approach to decomposing this into component categories for sourcing.",
    )
    report["reasoning_log"].append({"agent": "Ferrari Procurement", "timestamp": ts(), "thought": reasoning})

    total_parts = sum(c["parts_count"] for c in bom)
    report["bill_of_materials_summary"] = {
        "total_component_categories": len(bom),
        "total_unique_parts": total_parts,
        "categories": bom,
    }

    emit(
        "ferrari-procurement-01",
        "Ferrari Procurement",
        "system",
        "System",
        "bom_complete",
        summary=None,
        payload={"summary": f"BOM decomposed: {len(bom)} categories, {total_parts} unique parts"},
    )

    await asyncio.sleep(0.3)
    return bom
