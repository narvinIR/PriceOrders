import asyncio
import logging
from unittest.mock import AsyncMock, patch
from backend.services.llm_router import LlmRouter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_failover():
    print("\n🚀 Testing LLM Router Failover Logic...\n")

    router = LlmRouter()

    # 1. Simulate Gemini 429 (Too Many Requests)
    # We mock _try_gemini_relay to return None (as it does on 429/error)
    with patch.object(
        router, "_try_gemini_relay", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = None  # Simulate Failure

        # 2. Simulate Groq Success
        with patch(
            "backend.clients.groq_client.GroqClient.complete", new_callable=AsyncMock
        ) as mock_groq:
            mock_groq.return_value = "GROQ_RESPONSE"

            result = await router.completion("Test Prompt")

            # Assertions
            if result == "GROQ_RESPONSE":
                print(
                    "✅ Failover Verification PASSED: Gemini Failed -> Groq Succeeded"
                )
            else:
                print(f"❌ Failover Verification FAILED: Got {result}")

            # Verify calls
            print(f"   Gemini Called: {mock_gemini.called}")
            print(f"   Groq Called: {mock_groq.called}")


if __name__ == "__main__":
    asyncio.run(test_failover())
