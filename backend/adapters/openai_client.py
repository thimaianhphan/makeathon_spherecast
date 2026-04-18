from __future__ import annotations

from google import genai

from backend.config import GEMINI_API_KEY

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# Backwards-compat alias used by agent_service
def get_async_client() -> genai.Client:
    return get_gemini_client()
