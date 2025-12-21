import re
import unicodedata

# Синонимы материалов - приводим к полной форме
MATERIAL_SYNONYMS = {
    'пп': 'полипропилен',
    'pp': 'полипропилен',
    'пэ': 'полиэтилен',
    'pe': 'полиэтилен',
    'пвх': 'поливинилхлорид',
    'pvc': 'поливинилхлорид',
    'ппр': 'полипропилен',
    'ppr': 'полипропилен',
    'pert': 'полиэтилен',
    'pe-rt': 'полиэтилен',
}

# Синонимы типов товаров
PRODUCT_SYNONYMS = {
    'колено': 'отвод',
    'угол': 'отвод',
    'угольник': 'отвод',
    'elbow': 'отвод',
    'тройник': 'тройник',
    'tee': 'тройник',
    'муфта': 'муфта',
    'coupling': 'муфта',
    'заглушка': 'заглушка',
    'cap': 'заглушка',
    'plug': 'заглушка',
    'кан': 'канализационн',  # кан. → канализационн
    'нар кан': 'наружная канализация',
    'нар.кан': 'наружная канализация',
    'малошум': 'малошумная',
    'вн рез': 'внутренняя резьба',
    'вн.рез': 'внутренняя резьба',
    'нар рез': 'наружная резьба',
    'нар.рез': 'наружная резьба',
    'в р': 'внутренняя резьба',
    'в/р': 'внутренняя резьба',
    'н р': 'наружная резьба',
    'н/р': 'наружная резьба',
}

# Таблица соответствия диаметров труб (мм) размерам хомутов (дюймы)
PIPE_MM_TO_INCH = {
    15: '3/8"', 16: '3/8"', 19: '3/8"',
    20: '1/2"', 25: '1/2"',
    26: '3/4"', 30: '3/4"',
    32: '1"', 36: '1"',
    40: '1 1/4"', 46: '1 1/4"',
    50: '1 1/2"', 51: '1 1/2"',
    63: '2"', 65: '2"',
    75: '2 1/2"', 78: '2 1/2"',
    90: '3"', 92: '3"',
    110: '4"', 115: '4"',
    140: '5"', 142: '5"',
    160: '6"', 166: '6"',
}

def expand_synonyms(text: str) -> str:
    """Заменяет сокращения материалов и типов на полные формы"""
    result = text.lower()
    # Заменяем материалы (как отдельные слова)
    for abbr, full in MATERIAL_SYNONYMS.items():
        result = re.sub(rf'\b{re.escape(abbr)}\b', full, result)
    # Заменяем типы товаров (сортируем по длине - длинные первые)
    sorted_synonyms = sorted(PRODUCT_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True)
    for abbr, full in sorted_synonyms:
        result = re.sub(rf'\b{re.escape(abbr)}\.?\b', full, result)
    return result


def normalize_sku(sku: str) -> str:
    """Нормализация артикула для сравнения"""
    if not sku:
        return ""
    # Приводим к верхнему регистру
    result = sku.upper()
    # Убираем пробелы, дефисы, точки, слэши
    result = re.sub(r'[\s\-\.\/_]+', '', result)
    # Убираем leading zeros
    result = result.lstrip('0') or '0'
    return result

def normalize_name(name: str) -> str:
    """Нормализация названия товара для fuzzy matching"""
    if not name:
        return ""
    # Приводим к нижнему регистру
    result = name.lower()
    # Нормализуем Unicode
    result = unicodedata.normalize('NFKC', result)
    # Заменяем ё на е
    result = result.replace('ё', 'е')
    # Расширяем синонимы материалов и типов
    result = expand_synonyms(result)
    # Убираем информацию об упаковке штук (уп 20 шт), (20 шт)
    # НО сохраняем метраж (50 м), (100 м) - это разные товары!
    result = re.sub(r'\(уп\.?\s*\d+\s*шт\.?\)', '', result)
    result = re.sub(r'\(\d+\s*шт\)', '', result)
    # Убираем толщину в скобках (2.7), (2.2)
    result = re.sub(r'\(\d+\.\d+\)', '', result)
    # Убираем типы муфт/переходов для базового сопоставления
    result = re.sub(r'\(двухраструбная\)', '', result)
    # НО сохраняем "ремонтная" - это разные товары!
    result = re.sub(r'\(ремонтная\)', 'ремонтная', result)  # убираем скобки, слово оставляем
    result = re.sub(r'\bсоединительн\w*', '', result)  # соединительная/ый
    # Нормализуем переход/переходник
    result = re.sub(r'\bпереход\b', 'переходник', result)
    result = re.sub(r'\bэксц\.?\b', '', result)  # эксцентрический
    # Компенсатор кан. = Патрубок компенсационный
    result = re.sub(r'\bкомпенсатор\s+кан', 'патрубок компенсационный', result)
    # Хомут 110 → Хомут 4" (конвертация мм в дюймы)
    def convert_clamp_mm_to_inch(m):
        mm = int(m.group(1))
        inch = PIPE_MM_TO_INCH.get(mm, f'{mm}')
        return f'хомут в комплекте {inch}'
    result = re.sub(r'\bхомут\s+(\d+)\b', convert_clamp_mm_to_inch, result)
    # Убираем цвет - не важен для сопоставления
    result = re.sub(r'\bсерый\b', '', result)
    result = re.sub(r'\bбелый\b', '', result)
    # Нормализуем размеры труб: 110-2000, 110х50, 110*50, 110×50 → 110×50
    # Сначала унифицируем разделители (-, x, х, X, Х, *, ×) → ×
    result = re.sub(r'(\d+)\s*[-xхXХ*×]\s*(\d+)', r'\1×\2', result)
    # Убираем Jk/Jakko - весь каталог Jakko, не нужно для сравнения
    # НО оставляем Prestige - это линейка малошумной канализации!
    result = re.sub(r'\bjk\b', '', result)
    result = re.sub(r'\bjakko\b', '', result)
    # Унифицируем: малошумн* → prestige (для matching)
    result = re.sub(r'\bмалошумн\w*\b', 'prestige', result)
    # Нормализуем PN (давление): PN 10, PN-10, PN10 → pn10
    result = re.sub(r'\bpn\s*[-]?\s*(\d+)', r'pn\1', result)
    # Убираем лишние пробелы
    result = ' '.join(result.split())
    # Убираем знаки препинания кроме пробелов
    result = re.sub(r'[^\w\s]', ' ', result)
    result = ' '.join(result.split())
    return result

def extract_numeric_sku(sku: str) -> str:
    """Извлекает только цифры из артикула"""
    if not sku:
        return ""
    digits = re.sub(r'\D', '', sku)
    return digits.lstrip('0') or '0'

def tokenize_name(name: str) -> set[str]:
    """Разбивает название на токены для сравнения"""
    normalized = normalize_name(name)
    # Убираем стоп-слова
    stop_words = {'для', 'и', 'или', 'с', 'на', 'по', 'из', 'к', 'в', 'от', 'до', 'шт', 'мм', 'см', 'м', 'кг', 'г', 'л', 'мл'}
    tokens = set(normalized.split())
    return tokens - stop_words


def extract_pipe_size(name: str) -> tuple[int, int] | None:
    """
    Извлекает размеры трубы (диаметр×длина) из названия.
    Возвращает (diameter, length) или None если не найдено.

    Примеры:
        "Труба ПП 110×2000" → (110, 2000)
        "Труба 50x1500" → (50, 1500)
        "Труба 32-500" → (32, 500)
    """
    if not name:
        return None
    # Ищем паттерн: число × число (с разными разделителями)
    m = re.search(r'(\d+)\s*[×xхXХ*\-]\s*(\d+)', name)
    if m:
        diameter = int(m.group(1))
        length = int(m.group(2))
        # Валидация: диаметр 16-400мм, длина 100-6000мм
        if 16 <= diameter <= 400 and 100 <= length <= 6000:
            return (diameter, length)
    return None


def extract_fitting_size(name: str) -> tuple[int, ...] | None:
    """
    Извлекает размеры фитинга из названия (игнорируя углы).
    Может быть 1-3 размера: диаметр, или диаметр×диаметр (переход/тройник).

    Примеры:
        "Муфта ППР 32" → (32,)
        "Переход 50×32" → (50, 32)
        "Тройник 110/50" → (110, 50)
        "Тройник кан. 45° серый 110-50 Jakko" → (110, 50)
        "Крестовина кан. 87° серый 110-110 Jakko" → (110, 110)
    """
    if not name:
        return None

    # Убираем угол с градусами чтобы не путать с размером
    # 45°, 67°, 87°, 90° - это углы, не размеры
    clean_name = re.sub(r'\b(45|67|87|90)\s*°', '', name)

    # Ищем размеры фитингов в формате: 110-50, 110/50, 110×50, 110x50
    # Паттерн: большое_число разделитель маленькое_число (опционально третий)
    m = re.search(r'\b(\d{2,3})\s*[-/×xхXХ*]\s*(\d{2,3})(?:\s*[-/×xхXХ*]\s*(\d{2,3}))?\b', clean_name)
    if m:
        sizes = [int(s) for s in m.groups() if s]
        # Валидация: размеры фитингов 25-200мм (трубы канализации 32-160)
        if all(25 <= s <= 200 for s in sizes):
            return tuple(sizes)

    # Одиночный размер (Муфта 32, Заглушка 110, Сифон 50)
    # Ищем число 25-200 в любом месте названия после типа товара
    # Паттерн: тип товара ... число (через любые слова)
    name_lower = clean_name.lower()
    types_pattern = r'(муфт|заглуш|ревизи|крестовин|тройник|переход|отвод|сифон)'
    if re.search(types_pattern, name_lower):
        # Ищем все числа 25-200 в названии
        numbers = [int(n) for n in re.findall(r'\b(\d{2,3})\b', name_lower) if 25 <= int(n) <= 200]
        if numbers:
            return (numbers[0],)  # Берём первое подходящее число

    return None
