import re
from uuid import UUID
from fuzzywuzzy import fuzz
from backend.models.database import get_supabase_client
from backend.utils.normalizers import normalize_sku, normalize_name
from backend.config import settings
from backend.models.schemas import MatchResult
from backend.services.embeddings import get_embedding_matcher


def is_eco_product(name: str) -> bool:
    """Проверка является ли товар ЭКО (эконом) версией"""
    name_lower = name.lower()
    return 'эко' in name_lower or 'eko' in name_lower or '(2.2)' in name_lower


def extract_mm_from_clamp(client_name: str) -> int | None:
    """Извлечь размер в мм из запроса хомута"""
    m = re.search(r'\bхомут\s+(\d+)\b', client_name.lower())
    return int(m.group(1)) if m else None


def clamp_fits_mm(product_name: str, target_mm: int) -> bool:
    """Проверить подходит ли хомут по диапазону мм"""
    # Формат: (107-115) или (87-92)
    m = re.search(r'\((\d+)-(\d+)\)', product_name)
    if m:
        mm_min, mm_max = int(m.group(1)), int(m.group(2))
        return mm_min <= target_mm <= mm_max
    return False


class MatchingService:
    """7-уровневый алгоритм маппинга артикулов"""

    def __init__(self):
        self.db = get_supabase_client()
        self._products_cache = None
        self._mappings_cache = {}
        self._embedding_matcher = get_embedding_matcher()

    def _load_products(self) -> list[dict]:
        """Загрузка каталога товаров и построение embedding индекса"""
        if self._products_cache is None:
            response = self.db.table('products').select('*').execute()
            self._products_cache = response.data or []
            # Строим embedding индекс для семантического поиска
            if self._products_cache and not self._embedding_matcher.is_ready:
                try:
                    self._embedding_matcher.build_index(self._products_cache)
                except Exception:
                    pass  # ML не обязателен, продолжаем без него
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
        7-уровневый алгоритм маппинга:
        1. Точное совпадение артикула → 100%
        2. Точное совпадение названия → 95%
        3. Кэшированный маппинг → 100%
        4. Fuzzy SKU (Levenshtein dist ≤ 1) → 90%
        5. Fuzzy название (ratio ≥ 75) → 80%
        6. Semantic embedding (ML) → ≤75%
        7. Требует ручной проверки → 0%
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
            # Собираем все совпадения выше порога
            matches = []
            for product in products:
                prod_norm_name = normalize_name(product['name'])
                # Используем max из token_sort и token_set для лучшего покрытия
                ratio = max(
                    fuzz.token_sort_ratio(norm_name, prod_norm_name),
                    fuzz.token_set_ratio(norm_name, prod_norm_name)
                )
                if ratio >= settings.fuzzy_threshold:
                    matches.append((product, ratio))

            if matches:
                # Сортируем по ratio (убывание)
                matches.sort(key=lambda x: x[1], reverse=True)
                best_ratio = matches[0][1]

                # Фильтруем только лучшие (с отклонением <=2%)
                top_matches = [m for m in matches if m[1] >= best_ratio - 2]

                # Для хомутов - фильтруем по диапазону мм
                clamp_mm = extract_mm_from_clamp(client_name or "")
                if clamp_mm and len(top_matches) > 1:
                    fitting = [m for m in top_matches
                               if clamp_fits_mm(m[0]['name'], clamp_mm)]
                    if fitting:
                        top_matches = fitting

                # Если клиент НЕ указал ЭКО - предпочитаем стандарт
                client_wants_eco = is_eco_product(client_name or "")
                if not client_wants_eco and len(top_matches) > 1:
                    non_eco = [m for m in top_matches
                               if not is_eco_product(m[0]['name'])]
                    if non_eco:
                        top_matches = non_eco

                best_match, best_ratio = top_matches[0]
                conf = settings.confidence_fuzzy_name * (best_ratio / 100)
                # Повышаем confidence если выбрали правильный вариант
                if len(matches) > 1 and not client_wants_eco:
                    conf = min(conf + 5, 95.0)  # Бонус за выбор стандарта

                return MatchResult(
                    product_id=UUID(best_match['id']),
                    product_sku=best_match['sku'],
                    product_name=best_match['name'],
                    confidence=conf,
                    match_type="fuzzy_name",
                    needs_review=conf < settings.min_confidence_auto
                )

        # Level 7: Semantic embedding search (ML)
        if self._embedding_matcher.is_ready and client_name:
            result = self._embedding_matcher.get_best_match(client_name, min_score=0.6)
            if result:
                product, score = result
                # Конвертируем score (0-1) в confidence (0-100)
                conf = score * 100 * 0.75  # max 75% для ML (требует проверки)
                return MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=conf,
                    match_type="semantic_embedding",
                    needs_review=True  # ML всегда требует проверки
                )

        # Level 8: Не найдено - требует ручной проверки
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
