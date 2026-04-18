"""Intent Resolver Agent — expands high-level intent into sub-intents (graph expansion)."""

from __future__ import annotations

from backend.services.agent_service import ai_expand_intent, ai_decompose_bom


class IntentResolverService:
    """Resolves intent into component, logistics, and compliance sub-intents."""

    async def expand(self, intent: str) -> dict:
        """Expand intent into tree: root intent → leaf intents per domain."""
        expanded = await ai_expand_intent(intent)
        return {
            "root_intent": intent,
            "component_intents": expanded.get("component_intents", []),
            "logistics_intents": expanded.get("logistics_intents", []),
            "compliance_intents": expanded.get("compliance_intents", []),
        }

    async def expand_and_decompose(self, intent: str) -> tuple[dict, list[dict]]:
        """Expand intent and decompose into BOM categories."""
        expansion = await self.expand(intent)
        bom = await ai_decompose_bom(intent)
        return expansion, bom


intent_resolver = IntentResolverService()
