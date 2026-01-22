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
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


class EmbeddingMatcher:
    """Семантический поиск через FastEmbed (ONNX Local) + pgvector.
    Вектор: 384 dimensions (model: paraphrase-multilingual-MiniLM-L12-v2)
    """

    def __init__(self):
        self.db = get_supabase_client()
        logger.info(
            "📥 Loading FastEmbed model (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)..."
        )
        # Инициализация модели (скачивается один раз автоматически)
        self.model = TextEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        self._initialized = True

    def build_index(self, products: list[dict]) -> None:
        pass

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.5
    ) -> list[tuple[dict, float]]:
        """
        Семантический поиск товаров.
        """
        # 1. Подготовка текста
        embedding_text = prepare_embedding_text(query)
        if not embedding_text:
            return []

        # 2. Генерация через FastEmbed (быстрая, CPU)
        try:
            # list(generate) возвращает список векторов (нам нужен первый)
            embeddings = list(self.model.embed([embedding_text]))
            query_embedding = embeddings[0].tolist()
        except Exception as e:
            logger.error(f"FastEmbed generation failed: {e}")
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
