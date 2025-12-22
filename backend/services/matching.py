import re
import logging
from uuid import UUID
from fuzzywuzzy import fuzz
from backend.models.database import get_supabase_client
from backend.utils.normalizers import (
    normalize_sku, normalize_name, extract_pipe_size, extract_fitting_size,
    extract_thread_size
)
from backend.config import settings
from backend.models.schemas import MatchResult
from backend.services.embeddings import get_embedding_matcher
from backend.services.llm_matcher import get_llm_matcher

logger = logging.getLogger(__name__)


def detect_client_category(client_name: str) -> str | None:
    """
    Определить категорию из запроса клиента.
    Returns: 'prestige', 'outdoor', 'ppr', 'sewer', или None
    """
    name = client_name.lower()

    is_sewer = any(x in name for x in ['кан', 'канализац', 'сантех'])

    # Малошумная/Prestige = белая канализация (403)
    if any(x in name for x in ['малошум', 'prestige']):
        return 'prestige'
    # Белая + канализация = тоже Prestige
    if is_sewer and 'бел' in name:
        return 'prestige'

    # Наружная канализация = рыжая (303)
    if any(x in name for x in ['нар кан', 'нар.кан', 'наружн', 'рыж']):
        return 'outdoor'

    # ППР (водопровод/отопление) - белый, но НЕ канализация
    # "ПП" = полипропилен = ППР
    if any(x in name for x in ['ппр', 'ppr', 'водопровод', 'отоплен', ' пп ', 'пп ']):
        return 'ppr'
    if 'бел' in name and not is_sewer:
        return 'ppr'

    # Обычная серая канализация (202)
    if is_sewer or 'сер' in name:
        return 'sewer'

    return None  # Не указано - дефолт: обычная серая кан.


def extract_product_type(name: str) -> str | None:
    """
    Извлечь тип товара из названия.
    Returns: 'труба', 'отвод', 'тройник', 'муфта', 'заглушка', 'переходник',
             'ревизия', 'крестовина', 'патрубок', 'хомут', 'кран', 'фильтр',
             'клапан', 'сифон' или None
    """
    name_lower = name.lower()

    # Порядок важен - более специфичные первые
    # ВАЖНО: "ред" должен быть ДО "муфт", т.к. "Муфта ред." = "Муфта переходник"
    types = [
        ('крестовин', 'крестовина'),
        ('тройник', 'тройник'),
        ('переход', 'переходник'),
        ('ред', 'переходник'),  # "ред." = редукционный = переходник
        ('разъемн', 'муфта'),  # муфта разъемная = американка
        ('отвод', 'отвод'),
        ('колено', 'отвод'),
        ('угол', 'отвод'),
        ('муфт', 'муфта'),
        ('заглуш', 'заглушка'),
        ('ревизи', 'ревизия'),
        ('патруб', 'патрубок'),
        ('труб', 'труба'),
        ('хомут', 'хомут'),
        ('кран', 'кран'),
        ('фильтр', 'фильтр'),
        ('клапан', 'клапан'),
        ('сифон', 'сифон'),
    ]

    for marker, ptype in types:
        if marker in name_lower:
            return ptype
    return None


def extract_angle(name: str) -> int | None:
    """Извлечь угол из названия (15°, 30°, 45°, 67°, 87°, 90°)"""
    # Поддерживаем все углы, даже если в каталоге их нет
    m = re.search(r'\b(15|30|45|67|87|90)\s*[°градус]?', name.lower())
    if m:
        return int(m.group(1))
    # Альтернативный формат: /45, /90
    m = re.search(r'/\s*(15|30|45|67|87|90)\b', name.lower())
    if m:
        return int(m.group(1))
    return None


def normalize_angle(angle: int | None) -> int | None:
    """
    Нормализовать угол к стандартному каталогу Jakko.
    90° → 87° (в каталоге Jakko используется 87° вместо 90°)
    """
    if angle is None:
        return None
    if angle == 90:
        return 87  # Jakko convention: 87° вместо 90°
    return angle


def filter_by_category(matches: list, client_cat: str | None) -> list:
    """
    Фильтрует список совпадений по категории.
    matches: список (product, score) или просто product dicts
    """
    if not matches or len(matches) <= 1:
        return matches

    # Определяем формат: (product, score) или просто product
    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = None
    if client_cat == 'prestige':
        filtered = [m for m in matches
                    if 'малошум' in get_product(m).get('category', '').lower()
                    or 'prestige' in get_product(m)['name'].lower()]
    elif client_cat == 'outdoor':
        filtered = [m for m in matches
                    if 'наружн' in get_product(m).get('category', '').lower()
                    or 'нар.кан' in get_product(m)['name'].lower()]
    elif client_cat == 'ppr':
        filtered = [m for m in matches
                    if 'ппр' in get_product(m).get('category', '').lower()
                    or 'ппр' in get_product(m)['name'].lower()]
    else:
        # Дефолт: обычная СЕРАЯ канализация (202) - исключаем Prestige и наружную
        # Приоритет 1: SKU начинается с 202 (серая канализация)
        sku_202 = [m for m in matches
                   if get_product(m).get('sku', '').startswith('202')]
        if sku_202:
            return sku_202

        # Приоритет 2: Категория "канализация" (не малошум/наружная) или "серый" в названии
        filtered = [m for m in matches
                    if ('канализац' in get_product(m).get('category', '').lower()
                        and 'малошум' not in get_product(m).get('category', '').lower()
                        and 'наружн' not in get_product(m).get('category', '').lower())
                    or 'серый' in get_product(m)['name'].lower()]

    return filtered if filtered else matches


def filter_by_product_type(matches: list, client_type: str | None) -> list:
    """Фильтрует по типу товара (отвод, муфта, заглушка и т.д.)"""
    if not matches or not client_type or len(matches) <= 1:
        return matches

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = [m for m in matches
                if extract_product_type(get_product(m)['name']) == client_type]

    return filtered if filtered else matches


def filter_by_angle(matches: list, client_angle: int | None) -> list:
    """
    Фильтрует по углу (15°, 30°, 45°, 67°, 87°, 90°).
    90° нормализуется в 87° (Jakko convention).
    """
    if not matches or not client_angle or len(matches) <= 1:
        return matches

    # Нормализуем угол клиента (90° → 87°)
    normalized_angle = normalize_angle(client_angle)

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = [m for m in matches
                if extract_angle(get_product(m)['name']) == normalized_angle]

    return filtered if filtered else matches


def extract_thread_type(name: str) -> str | None:
    """Извлечь тип резьбы: 'вн' (внутренняя) или 'нар' (наружная)"""
    name_lower = name.lower()
    # Паттерны: в/р, вн.рез, вн. рез, внутр
    if any(x in name_lower for x in ['в/р', 'вн.рез', 'вн. рез', 'вн рез', 'внутр']):
        return 'вн'
    # Паттерны: н/р, нар.рез, нар. рез, наруж
    if any(x in name_lower for x in ['н/р', 'нар.рез', 'нар. рез', 'нар рез', 'наруж']):
        return 'нар'
    return None


def filter_by_thread(matches: list, client_thread: str | None) -> list:
    """Фильтрует по типу резьбы (внутренняя/наружная)"""
    if not matches or not client_thread or len(matches) <= 1:
        return matches

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    filtered = [m for m in matches
                if extract_thread_type(get_product(m)['name']) == client_thread]

    return filtered if filtered else matches


def filter_by_fitting_size(matches: list, client_size: tuple | None) -> list:
    """
    Фильтрует по размерам фитинга (110/50, 110/110 и т.д.)

    Логика:
    - Если клиент указал 2 размера (110/50) - ищем точное совпадение
    - Если клиент указал 1 размер (110) - предпочитаем одинаковые размеры (110-110),
      если нет - тогда ищем по первому размеру
    """
    if not matches or not client_size or len(matches) <= 1:
        return matches

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    # Если клиент указал 2+ размера - точное совпадение
    if len(client_size) >= 2:
        # Для 3 размеров (тройник переходник 40-25-40) - точное совпадение
        if len(client_size) == 3:
            filtered = [m for m in matches
                        if extract_fitting_size(get_product(m)['name']) == client_size]
            if filtered:
                return filtered
            # Fallback: ищем тройник с правильными крайними размерами
            outer1, inner, outer2 = client_size
            filtered = [m for m in matches
                        if (ps := extract_fitting_size(get_product(m)['name']))
                        and len(ps) >= 2
                        and ps[0] == outer1 and inner in ps]
            return filtered if filtered else matches

        # Для 2 размеров - точное совпадение
        filtered = [m for m in matches
                    if extract_fitting_size(get_product(m)['name']) == client_size]
        return filtered if filtered else matches

    # Если клиент указал 1 размер (110) - ищем товары с ОДНИМ размером или одинаковыми
    single_size = client_size[0]

    # Приоритет 1: Товары с одним размером (просто 110, без второго размера)
    # Это важно для отводов: "отвод 110" != "отвод 110-50"
    single_only = [m for m in matches
                   if (ps := extract_fitting_size(get_product(m)['name']))
                   and len(ps) == 1 and ps[0] == single_size]
    if single_only:
        return single_only

    # Приоритет 2: Одинаковые размеры (110-110, 50-50) - прямой тройник/муфта
    same_size = [m for m in matches
                 if extract_fitting_size(get_product(m)['name']) == (single_size, single_size)]
    if same_size:
        return same_size

    # Приоритет 3: Первый размер совпадает (110-50, 110-110) - fallback
    first_match = [m for m in matches
                   if (ps := extract_fitting_size(get_product(m)['name']))
                   and ps[0] == single_size]
    return first_match if first_match else matches


def filter_by_thread_size(matches: list, client_thread: tuple | None) -> list:
    """
    Фильтрует по размеру резьбы (32×1", 25×3/4" и т.д.)

    client_thread: (мм, дюймы) - например (32, "1")
    """
    if not matches or not client_thread or len(matches) <= 1:
        return matches

    is_tuple = isinstance(matches[0], tuple)

    def get_product(m):
        return m[0] if is_tuple else m

    mm, inches = client_thread
    # Ищем товары с таким же размером резьбы в названии
    # Форматы каталога: "32x1"", "32×1"", "32*1""
    filtered = []
    for m in matches:
        name = get_product(m)['name'].lower()
        # Проверяем наличие размера с резьбой
        if (f'{mm}x{inches}"' in name or
            f'{mm}×{inches}"' in name or
            f'{mm}*{inches}"' in name or
            f'{mm}-{inches}"' in name):
            filtered.append(m)

    return filtered if filtered else matches


def is_eco_product(name: str) -> bool:
    """
    Проверка является ли товар ЭКО (эконом) версией.

    Толщины стенок:
    - (1.8) для 32/40/50 мм = стандарт (не ЭКО)
    - (2.2) для 110 мм = ЭКО (тонкостенная)
    - (2.7) для 110 мм = стандарт
    """
    name_lower = name.lower()
    # (1.8) - стандарт для труб 32/40/50, явно не ЭКО
    if '(1.8)' in name_lower:
        return False
    return 'эко' in name_lower or 'eko' in name_lower or '(2.2)' in name_lower


def extract_mm_from_clamp(client_name: str) -> int | None:
    """Извлечь размер в мм из запроса хомута"""
    name = client_name.lower()
    if 'хомут' not in name:
        return None
    # Паттерны: "хомут 110", "хомут в комплекте 110"
    m = re.search(r'\bхомут\s+(?:в\s+комплекте\s+)?(\d+)\b', name)
    if m:
        mm = int(m.group(1))
        # Валидация: размеры хомутов 15-200мм
        if 15 <= mm <= 200:
            return mm
    return None


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
        self._stats = {
            'total': 0,
            'exact_sku': 0,
            'exact_name': 0,
            'cached_mapping': 0,
            'fuzzy_sku': 0,
            'fuzzy_name': 0,
            'llm_match': 0,
            'semantic_embedding': 0,
            'not_found': 0,
            'total_confidence': 0.0,
        }

    def _load_products(self) -> list[dict]:
        """Загрузка каталога товаров и построение embedding индекса"""
        if self._products_cache is None:
            response = self.db.table('products').select('*').execute()
            self._products_cache = response.data or []
            # Строим embedding индекс для семантического поиска (если включен)
            # ENABLE_ML_MATCHING=false по умолчанию (экономит ~500 МБ RAM)
            if settings.enable_ml_matching:
                if self._products_cache and not self._embedding_matcher.is_ready:
                    try:
                        logger.info("🔧 Загрузка ML модели для semantic matching...")
                        self._embedding_matcher.build_index(self._products_cache)
                        logger.info("✅ ML модель загружена")
                    except Exception as e:
                        logger.warning(f"⚠️ ML matching недоступен: {e}")
        return self._products_cache

    def _load_client_mappings(self, client_id: UUID | None) -> dict:
        """Загрузка маппингов клиента"""
        if client_id is None:
            return {}  # Без client_id возвращаем пустой словарь
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

    def get_stats(self) -> dict:
        """Получить статистику matching"""
        stats = self._stats.copy()
        if stats['total'] > 0:
            stats['avg_confidence'] = round(
                stats['total_confidence'] / stats['total'], 1
            )
            stats['success_rate'] = round(
                100 * (stats['total'] - stats['not_found']) / stats['total'], 1
            )
        else:
            stats['avg_confidence'] = 0.0
            stats['success_rate'] = 0.0
        return stats

    def reset_stats(self):
        """Сбросить статистику"""
        for key in self._stats:
            self._stats[key] = 0 if isinstance(self._stats[key], int) else 0.0

    def _update_stats(self, match: MatchResult):
        """Обновить статистику после match"""
        self._stats['total'] += 1
        self._stats['total_confidence'] += match.confidence
        if match.match_type in self._stats:
            self._stats[match.match_type] += 1

    def _finalize_match(self, match: MatchResult) -> MatchResult:
        """Финализировать результат: логирование + статистика"""
        self._update_stats(match)
        if match.product_id:
            logger.info(
                f"Matched: {match.match_type} @ {match.confidence:.0f}% "
                f"→ {match.product_sku}"
            )
        else:
            logger.warning(f"Not found: {match.match_type}")
        return match

    def match_item(self, client_id: UUID | None, client_sku: str, client_name: str = None) -> MatchResult:
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
        logger.debug(f"Matching: sku={client_sku!r}, name={client_name!r}")

        products = self._load_products()
        mappings = self._load_client_mappings(client_id)

        norm_sku = normalize_sku(client_sku)
        norm_name = normalize_name(client_name) if client_name else ""

        # Level 3: Проверяем кэшированный маппинг (приоритет)
        if norm_sku in mappings:
            mapping = mappings[norm_sku]
            product = next((p for p in products if str(p['id']) == str(mapping['product_id'])), None)
            if product:
                return self._finalize_match(MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku,
                    match_type="cached_mapping",
                    needs_review=False,
                    pack_qty=product.get('pack_qty', 1)
                ))

        # Level 1: Точное совпадение артикула
        for product in products:
            if normalize_sku(product['sku']) == norm_sku:
                return self._finalize_match(MatchResult(
                    product_id=UUID(product['id']),
                    product_sku=product['sku'],
                    product_name=product['name'],
                    confidence=settings.confidence_exact_sku,
                    match_type="exact_sku",
                    needs_review=False,
                    pack_qty=product.get('pack_qty', 1)
                ))

        # Level 2: Точное совпадение названия
        if norm_name:
            for product in products:
                if normalize_name(product['name']) == norm_name:
                    return self._finalize_match(MatchResult(
                        product_id=UUID(product['id']),
                        product_sku=product['sku'],
                        product_name=product['name'],
                        confidence=settings.confidence_exact_name,
                        match_type="exact_name",
                        needs_review=False,
                        pack_qty=product.get('pack_qty', 1)
                    ))

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
            return self._finalize_match(MatchResult(
                product_id=UUID(best_sku_match['id']),
                product_sku=best_sku_match['sku'],
                product_name=best_sku_match['name'],
                confidence=settings.confidence_fuzzy_sku * (best_sku_ratio / 100),
                match_type="fuzzy_sku",
                needs_review=best_sku_ratio < 95,
                pack_qty=best_sku_match.get('pack_qty', 1)
            ))

        # Level 5: Fuzzy название
        if norm_name:
            # Извлекаем параметры из клиентского запроса
            client_size = extract_pipe_size(client_name or "")
            client_fitting_size = extract_fitting_size(client_name or "")
            client_thread_size = extract_thread_size(client_name or "")
            client_cat = detect_client_category(client_name or "")
            client_type = extract_product_type(client_name or "")
            client_angle = extract_angle(client_name or "")
            clamp_mm = extract_mm_from_clamp(client_name or "")
            client_wants_eco = is_eco_product(client_name or "")

            # Собираем все совпадения выше порога
            matches = []
            for product in products:
                # Проверка точного размера (если указан)
                if client_size:
                    product_size = extract_pipe_size(product['name'])
                    if product_size and product_size != client_size:
                        continue

                prod_norm_name = normalize_name(product['name'])
                ratio = max(
                    fuzz.token_sort_ratio(norm_name, prod_norm_name),
                    fuzz.token_set_ratio(norm_name, prod_norm_name)
                )
                if ratio >= settings.fuzzy_threshold:
                    matches.append((product, ratio))

            if matches:
                # ВАЖНО: Сначала применяем критические фильтры ко ВСЕМ matches,
                # потом выбираем лучших. Иначе неправильный тип может иметь
                # более высокий score и вытеснить правильный.
                client_thread = extract_thread_type(client_name or "")

                # Фильтр по типу товара - применяем ко всем
                if client_type:
                    type_filtered = [m for m in matches
                                     if extract_product_type(m[0]['name']) == client_type]
                    if type_filtered:
                        matches = type_filtered

                # Фильтр по углу - применяем ко всем (с нормализацией 90° → 87°)
                if client_angle:
                    normalized_angle = normalize_angle(client_angle)
                    if normalized_angle:  # None = угол не существует (30° в старых данных)
                        angle_filtered = [m for m in matches
                                          if extract_angle(m[0]['name']) == normalized_angle]
                        if angle_filtered:
                            matches = angle_filtered

                # Фильтр по категории - применяем ко ВСЕМ matches (критично для муфт)
                # Иначе 604 (рифленые) могут иметь выше score чем 202 (канализация)
                # Если категория не указана - по умолчанию 'sewer' (серая канализация)
                effective_cat = client_cat or 'sewer'
                cat_filtered = filter_by_category(matches, effective_cat)
                if cat_filtered:
                    matches = cat_filtered

                # Теперь сортируем и берём top
                matches.sort(key=lambda x: x[1], reverse=True)
                best_ratio = matches[0][1]
                top_matches = [m for m in matches if m[1] >= best_ratio - 2]

                # Применяем оставшиеся фильтры
                top_matches = filter_by_thread(top_matches, client_thread)

                # Фильтр по размерам фитингов (110/50 vs 110/110)
                top_matches = filter_by_fitting_size(top_matches, client_fitting_size)

                # Фильтр по размеру резьбы (32×1" для муфт НР/ВР)
                top_matches = filter_by_thread_size(top_matches, client_thread_size)

                # Хомуты - фильтруем по диапазону мм
                if clamp_mm and len(top_matches) > 1:
                    fitting = [m for m in top_matches
                               if clamp_fits_mm(m[0]['name'], clamp_mm)]
                    if fitting:
                        top_matches = fitting

                # Если НЕ ЭКО - предпочитаем стандарт
                if not client_wants_eco and len(top_matches) > 1:
                    non_eco = [m for m in top_matches
                               if not is_eco_product(m[0]['name'])]
                    if non_eco:
                        top_matches = non_eco

                best_match, best_ratio = top_matches[0]
                conf = settings.confidence_fuzzy_name * (best_ratio / 100)
                if len(matches) > 1 and not client_wants_eco:
                    conf = min(conf + 5, 95.0)

                # Если confidence низкий (<75%) - проверить через LLM
                if conf < 75:
                    llm = get_llm_matcher()
                    if llm:
                        if not llm.is_ready:
                            llm.set_products(products)
                        llm_result = llm.match(client_name)
                        if llm_result and llm_result.get("sku"):
                            llm_conf = float(llm_result.get("confidence", 0))
                            if llm_conf > conf:
                                llm_product = next(
                                    (p for p in products
                                     if p["sku"] == llm_result["sku"]),
                                    None
                                )
                                if llm_product:
                                    return self._finalize_match(MatchResult(
                                        product_id=UUID(llm_product['id']),
                                        product_sku=llm_product['sku'],
                                        product_name=llm_product['name'],
                                        confidence=llm_conf,
                                        match_type="llm_match",
                                        needs_review=llm_conf < 80,
                                        pack_qty=llm_product.get('pack_qty', 1)
                                    ))

                return self._finalize_match(MatchResult(
                    product_id=UUID(best_match['id']),
                    product_sku=best_match['sku'],
                    product_name=best_match['name'],
                    confidence=conf,
                    match_type="fuzzy_name",
                    needs_review=conf < settings.min_confidence_auto,
                    pack_qty=best_match.get('pack_qty', 1)
                ))

        # Level 7: LLM matching через OpenRouter API
        llm = get_llm_matcher()
        if llm and client_name:
            # Инициализируем каталог если ещё не загружен
            if not llm.is_ready:
                llm.set_products(products)

            result = llm.match(client_name)
            if result and result.get("sku"):
                # Ищем товар по SKU из ответа LLM
                product = next(
                    (p for p in products if p["sku"] == result["sku"]),
                    None
                )
                if product:
                    # Post-validation: проверяем размер трубы
                    client_size = extract_pipe_size(client_name)
                    if client_size:
                        product_size = extract_pipe_size(product['name'])
                        if product_size and product_size != client_size:
                            # Размеры не совпадают - ищем правильный товар
                            logger.debug(f"LLM size mismatch: {client_size} vs {product_size}")
                            product = None  # Отклоняем LLM результат

                if product:
                    conf = float(result.get("confidence", 70))
                    return self._finalize_match(MatchResult(
                        product_id=UUID(product['id']),
                        product_sku=product['sku'],
                        product_name=product['name'],
                        confidence=conf,
                        match_type="llm_match",
                        needs_review=conf < 80,
                        pack_qty=product.get('pack_qty', 1)
                    ))

        # Fallback: Semantic embedding (если LLM недоступен)
        if self._embedding_matcher.is_ready and client_name:
            results = self._embedding_matcher.search(
                client_name, top_k=20, min_score=0.4
            )
            if results:
                client_cat = detect_client_category(client_name)
                client_type = extract_product_type(client_name)
                client_angle = extract_angle(client_name)
                client_thread = extract_thread_type(client_name)
                client_fitting_size = extract_fitting_size(client_name)
                client_thread_size = extract_thread_size(client_name)

                filtered = filter_by_product_type(results, client_type)
                filtered = filter_by_angle(filtered, client_angle)
                filtered = filter_by_thread(filtered, client_thread)
                filtered = filter_by_category(filtered, client_cat)
                filtered = filter_by_fitting_size(filtered, client_fitting_size)
                filtered = filter_by_thread_size(filtered, client_thread_size)

                if filtered:
                    product, score = filtered[0]
                    conf = score * 100 * 0.75
                    return self._finalize_match(MatchResult(
                        product_id=UUID(product['id']),
                        product_sku=product['sku'],
                        product_name=product['name'],
                        confidence=conf,
                        match_type="semantic_embedding",
                        needs_review=True,
                        pack_qty=product.get('pack_qty', 1)
                    ))

        # Level 8: Не найдено - требует ручной проверки
        return self._finalize_match(MatchResult(
            product_id=None,
            product_sku=None,
            product_name=None,
            confidence=0.0,
            match_type="not_found",
            needs_review=True
        ))

    def match_order_items(self, client_id: UUID, items: list[dict],
                          auto_save: bool = True) -> list[dict]:
        """
        Маппинг всех позиций заказа.

        Args:
            client_id: ID клиента
            items: Список позиций заказа
            auto_save: Автоматически сохранять маппинги с высоким confidence
        """
        results = []
        for item in items:
            client_sku = item.get('client_sku', '')
            match = self.match_item(
                client_id=client_id,
                client_sku=client_sku,
                client_name=item.get('client_name', '')
            )

            # Автосохранение высокоточных маппингов
            auto_saved = False
            if auto_save and client_sku:
                auto_saved = self.auto_save_high_confidence(client_id, client_sku, match)

            results.append({
                **item,
                'match': match.model_dump(),
                'auto_saved': auto_saved
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

    def auto_save_high_confidence(self, client_id: UUID, client_sku: str,
                                   match: MatchResult) -> bool:
        """
        Автосохранение маппингов с высоким confidence (≥95%).
        Сохраняет как unverified - требует ручного подтверждения.

        Returns:
            True если маппинг был сохранён
        """
        if (match.confidence >= settings.confidence_exact_name and
            match.product_id is not None and
            match.match_type in ("exact_sku", "exact_name", "cached_mapping")):
            try:
                self.save_mapping(
                    client_id=client_id,
                    client_sku=client_sku,
                    product_id=match.product_id,
                    confidence=match.confidence,
                    match_type=match.match_type,
                    verified=False  # Требует ручного подтверждения
                )
                return True
            except Exception:
                pass
        return False
