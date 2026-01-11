import logging
from uuid import UUID

from backend.models.schemas import MatchResult
from backend.services.matching_strategies.base import MatchingStrategy
from backend.services.llm_matcher import get_llm_matcher

logger = logging.getLogger(__name__)

class LlmStrategy(MatchingStrategy):
    """
    Стратегия матчинга через LLM (OpenRouter).
    Используется как fallback для сложных случаев.
    """

    def __init__(self):
        self._matcher = get_llm_matcher()

    def match(self,
              client_sku: str,
              client_name: str | None,
              products: list[dict],
              mappings: dict | None = None) -> MatchResult | None:
        
        if not self._matcher:
            # LLMMatcher может быть не инициализирован (нет API ключа)
            return None

        # Убеждаемся, что продукты загружены в кэш промпта
        if not self._matcher.is_ready and products:
            self._matcher.set_products(products)
            
        if not self._matcher.is_ready:
            logger.warning("LlmStrategy: Catalog not ready for LLM matching")
            return None

        # Используем client_name или client_sku как запрос
        query = client_name or client_sku
        
        # Вызываем LLM (это сетевой запрос, синхронная обертка над requests/httpx)
        # Note: LLMMatcher.match is synchronous/blocking as implemented in llm_matcher.py
        result = self._matcher.match(query)
        
        if not result or not result.get('sku'):
            return None
            
        found_sku = result['sku']
        confidence = result.get('confidence', 0.0)
        
        # Находим product_id по SKU
        product = next((p for p in products if p['sku'] == found_sku), None)
        
        if product:
            return MatchResult(
                product_id=product['id'],
                product_sku=product['sku'],
                product_name=product['name'],
                match_type='llm_match',
                confidence=confidence,
                needs_review=confidence < 85 # LLM результаты лучше проверять
            )
        else:
            # LLM вернул SKU, которого нет в базе (галлюцинация)
            logger.warning(f"LLM hallucinations: returned non-existent SKU {found_sku}")
            return None
