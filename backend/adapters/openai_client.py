from __future__ import annotations

from google import genai

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        # Picks up GEMINI_API_KEY from the environment automatically
        _client = genai.Client()
    return _client


# Backwards-compat alias used by agent_service
def get_async_client() -> genai.Client:
    return get_gemini_client()
