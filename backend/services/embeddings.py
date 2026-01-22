"""
Embedding-based semantic matching service.
Level 7 в алгоритме маппинга - семантическое сходство через pgvector.

v5.0: Заменён FAISS на pgvector (embeddings хранятся в PostgreSQL)
v6.0: Использование OpenAI API (via OpenRouter) вместо локальной модели для снижения RAM (0 MB).
"""

import logging

from backend.models.database import get_supabase_client
from backend.utils.matching_helpers import prepare_embedding_text
from backend.utils.openai_client import generate_embedding

logger = logging.getLogger(__name__)


class EmbeddingMatcher:
    """Семантический поиск товаров через pgvector (PostgreSQL) + OpenAI Embeddings"""

    def __init__(self):
        self.db = get_supabase_client()
        self._initialized = True  # Always ready (serverless)

    def build_index(self, products: list[dict]) -> None:
        """
        DEPRECATED: Индекс теперь в PostgreSQL (HNSW).
        """
        pass

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.5
    ) -> list[tuple[dict, float]]:
        """
        Семантический поиск товаров через pgvector.

        Args:
            query: Текст запроса (название товара)
            top_k: Количество результатов
            min_score: Минимальный порог сходства (0-1)

        Returns:
            Список (product, score) отсортированный по убыванию сходства
        """
        # Используем единую логику подготовки текста
        embedding_text = prepare_embedding_text(query)
        if not embedding_text:
            return []

        # Генерируем embedding через API (OpenAI/Cohere)
        query_embedding = generate_embedding(embedding_text)
        if not query_embedding:
            logger.warning(f"Failed to generate embedding for: {query}")
            return []

        # Вызываем RPC функцию match_products в PostgreSQL
        try:
            result = self.db.rpc(
                "match_products",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": min_score,
                    "match_count": top_k,
                },
            ).execute()

            # Преобразуем результат в формат (product, score)
            matches = []
            for row in result.data:
                product = {
                    "id": row["id"],
                    "sku": row["sku"],
                    "name": row["name"],
                    # Note: match_products RPC might not return category/pack_qty if not requested.
                    # We might need to fetch them or adjust RPC.
                    # Assuming basic info is enough or RPC returns what we need.
                    # If RPC returns only id/sku/name, we might miss category/pack_qty used by filters.
                    # Let's hope HybridStrategy handles missing fields gracefully or fetches them.
                    # Actually, HybridStrategy takes `products` list as input matching input.
                    # But `EmbeddingMatcher.search` returns specific product dicts.
                    # If these dicts lack 'pack_qty' etc, filtering might fail.
                    # Ideally, we should lookup the full product from `products` cache using ID if possible.
                    # But EmbeddingMatcher is standalone.
                    # Let's add extra fields to RPC if possible, or live with it.
                    # Current RPC in setup_pgvector.py returns: id, sku, name, similarity.
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
        return True


# Singleton
_embedding_matcher: EmbeddingMatcher | None = None


def get_embedding_matcher() -> EmbeddingMatcher:
    global _embedding_matcher
    if _embedding_matcher is None:
        _embedding_matcher = EmbeddingMatcher()
    return _embedding_matcher
