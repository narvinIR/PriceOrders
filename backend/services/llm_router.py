import logging
import asyncio
from typing import Optional

# Clients
# Assuming existing OpenRouter client or Google logic exists in llm_matcher.py
# We will use the existing helper from llm_matcher.py for the "Primary" logic
# but wrapping it might be tricky if it's not separated.
# Ideally, we refactor `llm_matcher.py` to be a client, OR we use LlmRouter to call different services.

import httpx
import json
import time

from backend.clients.groq_client import GroqClient

# We need a Gemini Client or reuse existing logic.
# Existing logic is likely in `backend/services/llm_matcher.py`.
# Let's inspect that file later, for now we assume we can call a function `call_gemini` or similar.

# Placeholder for Gemini call - will be replaced/connected to actual implementation
from backend.config import settings

logger = logging.getLogger(__name__)

# Cloudflare Worker relay (proxies to Google Gemini with embedded API key)
GEMINI_RELAY_URL = "https://gemini-api-relay.schmidvili1.workers.dev"
GEMINI_MODEL = "models/gemini-2.0-flash-001"


class LlmRouter:
    """
    Routes LLM requests to available free providers.
    Priority:
    1. Google Gemini (via Relay) - Free, High Limit but strict 429
    2. Groq (Llama 3) - Free, High Speed
    """

    def __init__(self):
        self.groq = GroqClient()

    async def completion(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """
        Try providers in order. Returns raw text content.
        """
        # 1. Try Google Gemini (Relay)
        result = await self._try_gemini_relay(prompt, system_prompt)
        if result:
            return result

        # 2. Try Groq
        logger.info("⚠️ Gemini failed or rate-limited. Falling back to Groq...")
        # Groq context window is large enough (8k/8k+ for Llama 3)
        result = await self.groq.complete(prompt, system_prompt)
        if result:
            logger.info("✅ Groq success.")
            return result

        logger.error("❌ All LLM providers failed.")
        return None

    async def _try_gemini_relay(self, prompt: str, system_prompt: str) -> Optional[str]:
        """
        Attempt to call Google Gemini via Relay.
        """
        url = f"{GEMINI_RELAY_URL}/v1beta/{GEMINI_MODEL}:generateContent"

        # Merge system prompt if present (Gemini API has system instruction but simple merging is safer for Relay)
        full_text = prompt
        if system_prompt:
            full_text = f"{system_prompt}\n\n{prompt}"

        payload = {
            "contents": [{"parts": [{"text": full_text}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 429:
                    logger.warning("Gemini Relay 429 (Rate Limit)")
                    return None

                if response.status_code != 200:
                    logger.warning(
                        f"Gemini Error {response.status_code}: {response.text[:100]}"
                    )
                    return None

                data = response.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, TypeError):
                    logger.error(f"Gemini malformed response: {data}")
                    return None

        except Exception as e:
            logger.warning(f"Gemini Relay Exception: {e}")
            return None


llm_router = LlmRouter()
