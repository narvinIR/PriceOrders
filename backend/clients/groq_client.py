import logging
import aiohttp
from backend.config import settings

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Client for Groq API (OpenAI-compatible)
    Docs: https://console.groq.com/docs/api-reference
    """

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model

    async def complete(self, prompt: str, system_prompt: str = None) -> str:
        """
        Send a completion request to Groq.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY is missing. Skipping Groq.")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Low temp for matching tasks
            "max_tokens": 1024,
        }

        max_retries = 3
        backoff = 2.0

        for attempt in range(max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.BASE_URL, headers=headers, json=payload, timeout=20
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data["choices"][0]["message"]["content"]
                        elif response.status == 429:
                            if attempt < max_retries:
                                logger.warning(
                                    f"Groq Rate Limit (429). Sleeping {backoff}s..."
                                )
                                import asyncio

                                await asyncio.sleep(backoff)
                                backoff *= 2
                                continue
                            else:
                                logger.error("Groq Rate Limit Exceeded (Max Retries).")
                                return None
                        else:
                            text = await response.text()
                            logger.error(f"Groq API Error {response.status}: {text}")
                            return None
            except Exception as e:
                logger.error(f"Groq Request Failed: {e}")
                if attempt < max_retries:
                    import asyncio

                    await asyncio.sleep(1)
                    continue
                return None
        return None
