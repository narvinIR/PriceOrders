from uuid import UUID
from fuzzywuzzy import fuzz
from backend.models.database import get_supabase_client
from backend.utils.normalizers import normalize_sku, normalize_name, extract_numeric_sku
from backend.config import settings
from backend.models.schemas import MatchResult

class MatchingService:
    """6-уровневый алгоритм маппинга артикулов"""

    def __init__(self):
        self.db = get_supabase_client()
        self._products_cache = None
        self._mappings_cache = {}

    def _load_products(self) -> list[dict]:
        """Загрузка каталога товаров"""
        if self._products_cache is None:
            response = self.db.table('products').select('*').execute()
            self._products_cache = response.data or []
        return self._products_cache

    def _load_client_mappings(self, client_id: UUID) -> dict:
        """Загрузка маппингов клиента"""
        client_key = str(client_id)
        if client_key not in self._mappings_cache:
            response = self.db.table('mappings')\
                .select('client_sku, product_id, confidence, match_type')\
                .eq('client_id', str(client_id))\
                .eq('verified', True)\
                .execute()
            self._mappings_cache[client_key] = {
                normalize_sku(m['client_sku']): m
                for m in (response.data or [])
            }
        return self._mappings_cache[client_key]

    def clear_cache(self):
        """Очистка кэша"""
        self._products_cache = None
        self._mappings_cache = {}

    def match_item(self, client_id: UUID, client_sku: str, client_name: str = None) -> MatchResult:
        """
        6-уровневый алгоритм маппинга:
        1. Точное совпадение артикула → 100%
        2. Точное совпадение названия → 95%
        3. Кэшированный маппинг → 100%
        4. Fuzzy SKU (Levenshtein dist ≤ 1) → 90%
        5. Fuzzy название (ratio > 85) → 80%
        6. Требует ручной проверки → 0%
        """
        products = self._load_products()
        mappings = self._load_client_mappings(client_id)

        norm_sku = normalize_sku(client_sku)
        norm_name = normalize_name(client_name) if client_name else ""

        # Level 3: Проверяем кэшированный маппинг (приоритет)
        if norm_sku in mappings:
            mapping = mappings[norm_sku]
            product = next((p for p in products if str(p['id']) == str(mapping['product_id'])), None)
            if product:
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku,
                    match_type="cached_mapping",
                    needs_review=False
                )

        # Level 1: Точное совпадение артикула
        for product in products:
            if normalize_sku(product['sku']) == norm_sku:
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku,
                    match_type="exact_sku",
                    needs_review=False
                )

        # Level 2: Точное совпадение названия
        if norm_name:
            for product in products:
                if normalize_name(product['name']) == norm_name:
                    return MatchResult(
                        product_id=UUID(product['id']),
                        product_sku=product['sku'],
                        product_name=product['name'],
                        confidence=settings.confidence_exact_name,
                        match_type="exact_name",
                        needs_review=False
                    )

        # Level 4: Fuzzy SKU (Levenshtein distance ≤ 1)
        best_sku_match = None
        best_sku_ratio = 0
        for product in products:
            prod_norm_sku = normalize_sku(product['sku'])
            ratio = fuzz.ratio(norm_sku, prod_norm_sku)
            if ratio > best_sku_ratio and ratio >= 90:
                best_sku_ratio = ratio
                best_sku_match = product

        if best_sku_match and best_sku_ratio >= 90:
            return MatchResult(
                product_id=UUID(best_sku_match['id']),
                product_sku=best_sku_match['sku'],
                product_name=best_sku_match['name'],
                confidence=settings.confidence_fuzzy_sku * (best_sku_ratio / 100),
                match_type="fuzzy_sku",
                needs_review=best_sku_ratio < 95
            )

        # Level 5: Fuzzy название
        if norm_name:
            best_name_match = None
            best_name_ratio = 0
            for product in products:
                prod_norm_name = normalize_name(product['name'])
                # Token sort ratio лучше для перестановок слов
                ratio = fuzz.token_sort_ratio(norm_name, prod_norm_name)
                if ratio > best_name_ratio and ratio >= settings.fuzzy_threshold:
                    best_name_ratio = ratio
                    best_name_match = product

            if best_name_match:
                confidence = settings.confidence_fuzzy_name * (best_name_ratio / 100)
                return MatchResult(
                    product_id=UUID(best_name_match['id']),
                    product_sku=best_name_match['sku'],
                    product_name=best_name_match['name'],
                    confidence=confidence,
                    match_type="fuzzy_name",
                    needs_review=confidence < settings.min_confidence_auto
                )

        # Level 6: Не найдено - требует ручной проверки
        return MatchResult(
            product_id=None,
            product_sku=None,
            product_name=None,
            confidence=0.0,
            match_type="not_found",
            needs_review=True
        )

    def match_order_items(self, client_id: UUID, items: list[dict]) -> list[dict]:
        """Маппинг всех позиций заказа"""
        results = []
        for item in items:
            match = self.match_item(
                client_id=client_id,
                client_sku=item.get('client_sku', ''),
                client_name=item.get('client_name', '')
            )
            results.append({
                **item,
                'match': match.model_dump()
            })
        return results

    def save_mapping(self, client_id: UUID, client_sku: str, product_id: UUID,
                     confidence: float, match_type: str, verified: bool = False):
        """Сохранение маппинга в БД"""
        data = {
            'client_id': str(client_id),
            'client_sku': client_sku,
            'product_id': str(product_id),
            'confidence': confidence,
            'match_type': match_type,
            'verified': verified
        }

        # Upsert - обновляем если существует
        self.db.table('mappings').upsert(
            data,
            on_conflict='client_id,client_sku'
        ).execute()

        # Инвалидируем кэш
        client_key = str(client_id)
        if client_key in self._mappings_cache:
            del self._mappings_cache[client_key]
