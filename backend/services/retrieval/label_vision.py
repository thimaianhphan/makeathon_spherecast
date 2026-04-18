"""
Label Vision — Agnes AI Supply Chain Manager.

Multimodal extraction from food label images.
Uses OpenAI vision (gpt-4o-mini or gpt-4o) to extract:
  - ingredient list, allergens, certification logos, E-numbers.

Activated only when ENABLE_LABEL_VISION=true and an image path/URL is provided.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Optional

from backend.config import ENABLE_LABEL_VISION


@dataclass
class LabelExtract:
    source: str  # file path or URL
    ingredients: list[str] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    e_numbers: list[str] = field(default_factory=list)
    raw_text: str = ""
    error: str = ""
    confidence: float = 0.0


LABEL_VISION_PROMPT = """You are a food label analyst. Examine this food product label image and extract:
1. Full ingredient list (as a JSON array of strings)
2. Allergen declarations (as a JSON array matching EU 14 allergens where applicable)
3. Certification logos visible (e.g. Kosher, Halal, Organic, Non-GMO, FSSC22000, Vegan, etc.)
4. EU additive E-numbers mentioned (e.g. E322, E471)

Respond ONLY with valid JSON:
{
  "ingredients": ["..."],
  "allergens": ["..."],
  "certifications": ["..."],
  "e_numbers": ["..."],
  "confidence": 0.0
}"""


async def extract_from_image(source: str) -> LabelExtract:
    """
    Extract food label data from image at `source` (local path or URL).
    Returns LabelExtract with parsed data.
    """
    if not ENABLE_LABEL_VISION:
        return LabelExtract(source=source, error="Label vision disabled (ENABLE_LABEL_VISION=false)")

    try:
        from google import genai
        from google.genai import types as gtypes
        from backend.config import GEMINI_API_KEY, GEMINI_MODEL
        import json

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Build image part
        if source.startswith("http://") or source.startswith("https://"):
            import httpx
            img_bytes = httpx.get(source, timeout=10).content
            ext = source.rsplit(".", 1)[-1].lower()
        else:
            with open(source, "rb") as f:
                img_bytes = f.read()
            ext = os.path.splitext(source)[1].lower().lstrip(".")

        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                      "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")

        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                gtypes.Part.from_text(LABEL_VISION_PROMPT),
                gtypes.Part.from_bytes(data=img_bytes, mime_type=media_type),
            ],
            config=gtypes.GenerateContentConfig(max_output_tokens=800),
        )

        raw = response.text or ""
        # Parse JSON
        import re
        json_match = re.search(r"\{[\s\S]+\}", raw)
        if json_match:
            data = json.loads(json_match.group(0))
            return LabelExtract(
                source=source,
                ingredients=data.get("ingredients", []),
                allergens=data.get("allergens", []),
                certifications=data.get("certifications", []),
                e_numbers=data.get("e_numbers", []),
                raw_text=raw,
                confidence=float(data.get("confidence", 0.75)),
            )
        return LabelExtract(source=source, raw_text=raw, error="Could not parse JSON from vision response",
                            confidence=0.3)

    except Exception as exc:
        return LabelExtract(source=source, error=str(exc)[:200])
