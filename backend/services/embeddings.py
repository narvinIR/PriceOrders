"""
Embedding-based semantic matching service.
Level 7 в алгоритме маппинга - семантическое сходство через pgvector.

v7.2: Google Gemini Embeddings via Cloudflare Relay
- Added retry logic with exponential backoff
- Free, 0 RAM, No API Key needed
"""

import logging
import time
import httpx

from backend.models.database import get_supabase_client
from backend.utils.matching_helpers import prepare_embedding_text

logger = logging.getLogger(__name__)

# Cloudflare Worker relay (proxies to Google Gemini with embedded API key)
GEMINI_RELAY_URL = "https://gemini-api-relay.schmidvili1.workers.dev"
EMBEDDING_MODEL = "models/text-embedding-004"

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds


class EmbeddingMatcher:
    """Семантический поиск через Google Gemini Embeddings (via Relay) + pgvector.
    Вектор: 768 dimensions (model: text-embedding-004)
    """

    def __init__(self):
        self.db = get_supabase_client()
        self._initialized = True
        logger.info("✅ Gemini Embeddings configured (via Cloudflare Relay)")

    def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding using Google Gemini API via Cloudflare Relay.

        Includes retry logic with exponential backoff for reliability.
        """
        url = f"{GEMINI_RELAY_URL}/v1beta/{EMBEDDING_MODEL}:embedContent"
        payload = {
            "model": EMBEDDING_MODEL,
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_DOCUMENT",
        }

        backoff = INITIAL_BACKOFF
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("embedding", {}).get("values", [])
                    if embedding:
                        return embedding
                    else:
                        logger.error(f"No embedding in response: {data}")
                        return None
                elif response.status_code >= 500:
                    # Server error, retry
                    last_error = f"Server error {response.status_code}"
                    logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: {last_error}")
                else:
                    # Client error, don't retry
                    logger.error(
                        f"Gemini API error: {response.status_code} - {response.text}"
                    )
                    return None

            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: {last_error}")
            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: {last_error}")

            # Wait before retry (exponential backoff)
            if attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

        logger.error(
            f"Gemini embedding failed after {MAX_RETRIES} attempts: {last_error}"
        )
        return None

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.5
    ) -> list[tuple[dict, float]]:
        """Семантический поиск товаров."""
        if not self._initialized:
            return []

        # 1. Подготовка текста
        embedding_text = prepare_embedding_text(query)
        if not embedding_text:
            return []

        # 2. Генерация через Gemini Relay
        query_embedding = self._generate_embedding(embedding_text)
        if not query_embedding:
            return []

        # 3. Поиск в БД
        try:
            result = self.db.rpc(
                "match_products",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": min_score,
                    "match_count": top_k,
                },
            ).execute()

            matches = []
            for row in result.data:
                product = {
                    "id": row["id"],
                    "sku": row["sku"],
                    "name": row["name"],
                }
                matches.append((product, row["similarity"]))

            return matches

        except Exception as e:
            logger.error(f"pgvector search error: {e}")
            return []

    def get_best_match(
        self, query: str, min_score: float = 0.6
    ) -> tuple[dict, float] | None:
        results = self.search(query, top_k=1, min_score=min_score)
        return results[0] if results else None

    @property
    def is_ready(self) -> bool:
        return self._initialized


# Singleton
_embedding_matcher: EmbeddingMatcher | None = None


def get_embedding_matcher() -> EmbeddingMatcher:
    global _embedding_matcher
    if _embedding_matcher is None:
        _embedding_matcher = EmbeddingMatcher()
    return _embedding_matcher
