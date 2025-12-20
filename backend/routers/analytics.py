"""
API для аналитики и статистики matching.
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Глобальный экземпляр matcher для статистики
_matching_service = None


def get_matching_service():
    """Получить глобальный экземпляр MatchingService"""
    global _matching_service
    if _matching_service is None:
        from backend.services.matching import MatchingService
        _matching_service = MatchingService()
    return _matching_service


class MatchingStats(BaseModel):
    """Статистика matching"""
    total: int
    exact_sku: int
    exact_name: int
    cached_mapping: int
    fuzzy_sku: int
    fuzzy_name: int
    semantic_embedding: int
    not_found: int
    total_confidence: float
    avg_confidence: float
    success_rate: float


@router.get("/matching/stats", response_model=MatchingStats)
async def get_matching_stats():
    """
    Получить статистику matching.

    Возвращает количество совпадений по каждому уровню алгоритма,
    средний confidence и процент успешных совпадений.
    """
    matcher = get_matching_service()
    return matcher.get_stats()


@router.post("/matching/stats/reset")
async def reset_matching_stats():
    """
    Сбросить статистику matching.

    Полезно для начала нового сеанса тестирования.
    """
    matcher = get_matching_service()
    matcher.reset_stats()
    return {"status": "ok", "message": "Статистика сброшена"}


@router.get("/matching/levels")
async def get_matching_levels():
    """
    Информация об уровнях matching алгоритма.

    Полезно для документации и понимания работы системы.
    """
    return {
        "levels": [
            {
                "level": 1,
                "type": "exact_sku",
                "description": "Точное совпадение артикула",
                "confidence": 100,
                "needs_review": False
            },
            {
                "level": 2,
                "type": "exact_name",
                "description": "Точное совпадение названия после нормализации",
                "confidence": 95,
                "needs_review": False
            },
            {
                "level": 3,
                "type": "cached_mapping",
                "description": "Сохранённый маппинг клиента",
                "confidence": 100,
                "needs_review": False
            },
            {
                "level": 4,
                "type": "fuzzy_sku",
                "description": "Fuzzy SKU (Levenshtein ≤ 1)",
                "confidence": "~90",
                "needs_review": "если < 95%"
            },
            {
                "level": 5,
                "type": "fuzzy_name",
                "description": "Fuzzy название (token_sort + token_set)",
                "confidence": "~80",
                "needs_review": "если < 75%"
            },
            {
                "level": 6,
                "type": "semantic_embedding",
                "description": "ML семантический поиск",
                "confidence": "≤75",
                "needs_review": True
            },
            {
                "level": 7,
                "type": "not_found",
                "description": "Не найдено - требует ручной проверки",
                "confidence": 0,
                "needs_review": True
            },
        ]
    }
