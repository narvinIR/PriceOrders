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
        initial_confidence = result.get('confidence', 0.0)
        
        # Находим product_id по SKU
        product = next((p for p in products if p['sku'] == found_sku), None)
        
        if not product:
            logger.warning(f"LLM hallucinations: returned non-existent SKU {found_sku}")
            return None

        # --- Post-Validation Logic ---
        from backend.utils.matching_helpers import extract_product_type, extract_thread_type

        validation_log = []
        final_confidence = initial_confidence
        
        # 1. Проверка типа продукта (Отвод vs Муфта vs Тройник)
        client_type = extract_product_type(query)
        llm_type = extract_product_type(product['name'])
        
        if client_type and llm_type and client_type != llm_type:
            # Жесткий штраф за неверный тип (Отвод != Муфта)
            # Исключение: иногда "угол" = "отвод", это обрабатывается в extract_product_type
            # Но если типы реально разные:
            logger.warning(f"LLM Type Mismatch: Client '{client_type}' vs LLM '{llm_type}'")
            final_confidence = 0
            validation_log.append(f"Type mismatch: {client_type}!={llm_type}")

        # 2. Проверка типа резьбы (Вн vs Нар)
        # Актуально только если клиент явно указал резьбу
        client_thread = extract_thread_type(query)
        llm_thread = extract_thread_type(product['name'])
        
        if client_thread and llm_thread and client_thread != llm_thread:
            logger.warning(f"LLM Thread Mismatch: Client '{client_thread}' vs LLM '{llm_thread}'")
            final_confidence = 0
            validation_log.append(f"Thread mismatch: {client_thread}!={llm_thread}")

        # 3. Если уверенность стала 0 - отбрасываем
        if final_confidence <= 10:
             logger.info(f"LLM Match rejected by validation: {validation_log}")
             return None

        return MatchResult(
            product_id=product['id'],
            product_sku=product['sku'],
            product_name=product['name'],
            match_type='llm_match',
            confidence=final_confidence,
            needs_review=final_confidence < 85
        )
