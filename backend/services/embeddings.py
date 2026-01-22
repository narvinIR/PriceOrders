"""
Embedding-based semantic matching service.
Level 7 в алгоритме маппинга - семантическое сходство через pgvector.

v5.0: Заменён FAISS на pgvector (embeddings хранятся в PostgreSQL)
v6.0: Использование OpenAI API (via OpenRouter) вместо локальной модели для снижения RAM (0 MB).
"""

import logging
import time

from backend.models.database import get_supabase_client
from backend.utils.matching_helpers import prepare_embedding_text

# Local ML Model
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingMatcher:
    """Семантический поиск товаров через pgvector (PostgreSQL) + Local Embeddings (rubert-tiny2)"""

    def __init__(self):
        self.db = get_supabase_client()
        logger.info("📥 Loading local embedding model (cointegrated/rubert-tiny2)...")
        self.model = SentenceTransformer("cointegrated/rubert-tiny2")
        self._initialized = True

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

        # Генерируем embedding локально
        try:
            query_embedding = self.model.encode(embedding_text).tolist()
        except Exception as e:
            logger.error(f"Local embedding generation failed: {e}")
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
