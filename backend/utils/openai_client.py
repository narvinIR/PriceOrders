from openai import OpenAI
from backend.config import settings

# Global OpenAI client
_openai_client = None


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        if settings.openrouter_api_key:
            _openai_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )
        elif settings.openai_api_key:  # Fallback if standard env var used
            _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def generate_embedding(text: str, model: str = None) -> list[float]:
    """Generate embedding using OpenAI/OpenRouter"""
    client = get_openai_client()
    if not client:
        return []

    # Model selection: prefer config, fallback to default
    # If using OpenRouter, "openai/text-embedding-3-small" is safer
    # But let's assume settings.llm_model might be for chat,
    # we need separate setting for embedding model presumably?
    # Or just hardcode a good default matching the script.
    model_id = "openai/text-embedding-3-small"

    try:
        response = client.embeddings.create(model=model_id, input=text)
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return []
