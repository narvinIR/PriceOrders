"""
Embedding-based semantic matching service.
Level 7 в алгоритме маппинга - семантическое сходство через pgvector.

v5.0: Заменён FAISS на pgvector (embeddings хранятся в PostgreSQL)
v5.1: Усиление типа товара в embeddings для лучшего matching
"""
import logging
from typing import Optional
from backend.utils.normalizers import normalize_name
from backend.models.database import get_supabase_client

logger = logging.getLogger(__name__)


def prepare_embedding_text(name: str) -> str:
    """
    Подготовка текста для embedding с усилением типа товара.
    Тип товара добавляется дважды для повышения его веса.
    """
    # Lazy import to avoid circular dependency
    from backend.services.matching import extract_product_type

    norm = normalize_name(name)
    product_type = extract_product_type(name)
    if product_type:
        return f"{product_type} {product_type} {norm}"
    return norm

# Ленивая загрузка модели
_model = None


def _get_model():
    """Ленивая загрузка модели sentence-transformers"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model


class EmbeddingMatcher:
    """Семантический поиск товаров через pgvector (PostgreSQL)"""

    def __init__(self):
        self.db = get_supabase_client()
        self._initialized = True  # pgvector всегда готов

    def build_index(self, products: list[dict]) -> None:
        """
        DEPRECATED: Индекс теперь в PostgreSQL (HNSW).
        Метод оставлен для совместимости, ничего не делает.
        """
        pass

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5
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
        # Используем тот же формат что и при генерации embeddings
        embedding_text = prepare_embedding_text(query)
        if not embedding_text:
            return []

        model = _get_model()

        # Генерируем embedding для запроса
        query_embedding = model.encode(
            embedding_text,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

        # Вызываем RPC функцию match_products в PostgreSQL
        try:
            result = self.db.rpc('match_products', {
                'query_embedding': query_embedding,
                'match_threshold': min_score,
                'match_count': top_k
            }).execute()

            # Преобразуем результат в формат (product, score)
            matches = []
            for row in result.data:
                product = {
                    'id': row['id'],
                    'sku': row['sku'],
                    'name': row['name'],
                    'category': row.get('category'),
                    'pack_qty': row.get('pack_qty', 1),
                }
                matches.append((product, row['similarity']))

            return matches

        except Exception as e:
            logger.error(f"pgvector search error: {e}")
            return []

    def get_best_match(
        self,
        query: str,
        min_score: float = 0.6
    ) -> Optional[tuple[dict, float]]:
        """
        Получить лучшее совпадение.

        Args:
            query: Текст запроса
            min_score: Минимальный порог (default 0.6 = 60% сходства)

        Returns:
            (product, score) или None
        """
        results = self.search(query, top_k=1, min_score=min_score)
        return results[0] if results else None

    @property
    def is_ready(self) -> bool:
        """pgvector всегда готов - embeddings хранятся в PostgreSQL"""
        return True


# Singleton для использования во всём приложении
_embedding_matcher: Optional[EmbeddingMatcher] = None


def get_embedding_matcher() -> EmbeddingMatcher:
    """Получить глобальный экземпляр EmbeddingMatcher"""
    global _embedding_matcher
    if _embedding_matcher is None:
        _embedding_matcher = EmbeddingMatcher()
    return _embedding_matcher
