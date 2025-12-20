"""
Embedding-based semantic matching service.
Level 7 в алгоритме маппинга - семантическое сходство через ML.
"""
import numpy as np
from typing import Optional
from backend.utils.normalizers import normalize_name

# Ленивая загрузка тяжёлых зависимостей
_model = None
_faiss = None


def _get_model():
    """Ленивая загрузка модели sentence-transformers"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model


def _get_faiss():
    """Ленивая загрузка faiss"""
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


class EmbeddingMatcher:
    """Семантический поиск товаров через embeddings"""

    def __init__(self):
        self.index: Optional[object] = None
        self.products: list[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self._initialized = False

    def build_index(self, products: list[dict]) -> None:
        """
        Построение FAISS индекса для быстрого поиска.
        Вызывать при загрузке/обновлении каталога.
        """
        if not products:
            return

        model = _get_model()
        faiss = _get_faiss()

        # Нормализуем названия перед кодированием
        names = [normalize_name(p.get('name', '')) for p in products]

        # Создаём embeddings
        embeddings = model.encode(
            names,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        # Строим FAISS индекс (Inner Product = косинусное сходство для нормализованных векторов)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings.astype('float32'))

        self.products = products
        self.embeddings = embeddings
        self._initialized = True

    def search(self, query: str, top_k: int = 5, min_score: float = 0.5) -> list[tuple[dict, float]]:
        """
        Семантический поиск товаров.

        Args:
            query: Текст запроса (название товара)
            top_k: Количество результатов
            min_score: Минимальный порог сходства (0-1)

        Returns:
            Список (product, score) отсортированный по убыванию сходства
        """
        if not self._initialized or not self.index:
            return []

        model = _get_model()

        # Нормализуем запрос
        norm_query = normalize_name(query)
        if not norm_query:
            return []

        # Кодируем запрос
        query_embedding = model.encode(
            [norm_query],
            normalize_embeddings=True,
            show_progress_bar=False
        )

        # Поиск ближайших соседей
        scores, indices = self.index.search(
            query_embedding.astype('float32'),
            min(top_k, len(self.products))
        )

        # Фильтруем по минимальному порогу
        results = []
        for i, (idx, score) in enumerate(zip(indices[0], scores[0])):
            if idx >= 0 and score >= min_score:
                results.append((self.products[idx], float(score)))

        return results

    def get_best_match(self, query: str, min_score: float = 0.6) -> Optional[tuple[dict, float]]:
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
        """Проверка готовности индекса"""
        return self._initialized and self.index is not None


# Singleton для использования во всём приложении
_embedding_matcher: Optional[EmbeddingMatcher] = None


def get_embedding_matcher() -> EmbeddingMatcher:
    """Получить глобальный экземпляр EmbeddingMatcher"""
    global _embedding_matcher
    if _embedding_matcher is None:
        _embedding_matcher = EmbeddingMatcher()
    return _embedding_matcher
