"""
AI-powered supply chain agents with OpenAI reasoning.

Each agent is an independent actor that can:
- Reason about decisions using OpenAI
- Communicate via the message schema
- Be discovered through the registry
"""

from __future__ import annotations

import asyncio
import copy
import json

from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from backend.adapters.openai_client import get_gemini_client
from backend.config import GEMINI_MODEL


def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate" in msg or "resource_exhausted" in msg
from backend.agents import (
    a2a_agents,
    CATEGORY_AGENT_MAP,
    compliance_agents,
    core_agents,
    disqualified_agents,
    logistics_agents,
    mcp_agents,
    supplier_agents,
)
from backend.schemas import AgentFact


# ── Gemini reasoning helper ──────────────────────────────────────────────────


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _call_gemini(client, prompt: str, system_instruction: str) -> str:
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=8192,
        ),
    )
    return response.text.strip()


async def ai_reason(agent_name: str, role: str, prompt: str) -> str:
    """Ask Gemini to reason as a specific supply-chain agent."""
    try:
        client = get_gemini_client()
        system_instruction = (
            f"You are {agent_name}, a {role} in the Agnes AI Supply Chain Manager network "
            "for CPG (Consumer Packaged Goods) companies. "
            "You make realistic business decisions about food ingredient procurement, "
            "EU regulatory compliance, and supplier consolidation. "
            "Be concise (2-3 sentences). "
            "Respond with business reasoning only, no markdown."
        )
        result = await _call_gemini(client, prompt, system_instruction)
        print(f"Agent {agent_name} [{role}] → {result[:120]}")
        return result
    except Exception as e:
        return f"[Reasoning unavailable: {e}]"


async def ai_expand_intent(intent: str) -> dict:
    """Expand high-level intent into component, logistics, and compliance sub-intents."""
    try:
        client = get_gemini_client()
        system_instruction = (
            "You are an intent resolver for Agnes, the AI Supply Chain Manager for CPG companies. "
            "Given a procurement intent for food ingredients, "
            "return ONLY valid JSON object with keys: component_intents, logistics_intents, compliance_intents. "
            'component_intents: array of ingredient sourcing intents (e.g. "Source EU-approved emulsifiers"). '
            'logistics_intents: array of logistics intents (e.g. "Coordinate food-grade transport to EU manufacturing sites"). '
            'compliance_intents: array of compliance intents (e.g. "Validate EU 1333/2008 additive approval"). '
            "Each array should have 1-3 items."
        )
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=intent,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=8192,
            ),
        )
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text)
    except Exception:
        return {
            "component_intents": [f"Source ingredients for {intent[:80]}"],
            "logistics_intents": ["Coordinate EU food-grade transport to manufacturing sites"],
            "compliance_intents": ["Validate EU 1333/2008 additive approval and EU 1169/2011 allergen labelling"],
        }


async def ai_decompose_bom(intent: str) -> list[dict]:
    """Use Gemini to decompose an intent into a Bill of Materials for CPG ingredients."""
    try:
        client = get_gemini_client()
        system_instruction = (
            "You are a CPG food production engineer. Given a procurement intent, "
            "decompose it into ingredient categories needed. Return ONLY valid JSON array. "
            'Each item: {"category": str, "parts_count": int, '
            '"key_components": [str, str, str]}. '
            "Include relevant CPG ingredient categories: emulsifiers, sweeteners, fats_oils, "
            "flavourings, preservatives, antioxidants, proteins, starches, acids, vitamins."
        )
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=intent,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=8192,
            ),
        )
        text = response.text.strip()
        return _parse_json_array(text)
    except (json.JSONDecodeError, KeyError, IndexError):
        return _default_bom()
    except Exception:
        return _default_bom()


DEFAULT_BOM: list[dict] = [
    {
        "category": "emulsifiers",
        "parts_count": 2,
        "key_components": ["Lecithin (Soy-based, E322)", "Sunflower Lecithin (E322)"],
    },
    {
        "category": "sweeteners",
        "parts_count": 2,
        "key_components": ["Sucrose (Cane Sugar)", "Stevia Extract (E960)"],
    },
    {
        "category": "fats_oils",
        "parts_count": 2,
        "key_components": ["Sunflower Oil (Refined)", "Palm Oil (Certified RSPO)"],
    },
    {
        "category": "proteins",
        "parts_count": 2,
        "key_components": ["Whey Protein Concentrate (WPC80)", "Pea Protein Isolate (Organic)"],
    },
    {
        "category": "starches",
        "parts_count": 3,
        "key_components": ["Corn Starch (E1400)", "Rice Flour (Gluten-Free)", "Potato Starch (Organic)"],
    },
    {
        "category": "flavourings",
        "parts_count": 2,
        "key_components": ["Natural Vanilla Flavouring", "Cocoa Powder (10-12% Fat)"],
    },
    {
        "category": "antioxidants",
        "parts_count": 2,
        "key_components": ["Tocopherol Mix (E306)", "Rosemary Extract (E392)"],
    },
    {
        "category": "acids",
        "parts_count": 2,
        "key_components": ["Citric Acid (E330)", "Ascorbic Acid (Vitamin C, E300)"],
    },
]


def _parse_json_array(text: str) -> list[dict]:
    """Extract and parse a JSON array from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1].strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def _default_bom() -> list[dict]:
    return copy.deepcopy(DEFAULT_BOM)


# ── Seed Data: Pre-built AgentFacts for all supply chain actors ─────────────


def create_seed_agents() -> list[AgentFact]:
    """Create realistic supplier agents for the Ferrari supply chain."""
    return (
        core_agents()
        + supplier_agents()
        + logistics_agents()
        + compliance_agents()
        + disqualified_agents()
        + mcp_agents()
        + a2a_agents()
    )
