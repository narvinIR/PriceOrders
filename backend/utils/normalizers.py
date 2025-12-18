import re
import unicodedata

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
    # Убираем информацию об упаковке (уп 20 шт), (20 шт) и т.д.
    result = re.sub(r'\(уп\.?\s*\d+\s*шт\.?\)', '', result)
    result = re.sub(r'\(\d+\s*шт\)', '', result)
    result = re.sub(r'\(\d+\s*м\)', '', result)
    # Убираем толщину в скобках (2.7), (2.2)
    result = re.sub(r'\(\d+\.\d+\)', '', result)
    # Убираем типы муфт/переходов для базового сопоставления
    result = re.sub(r'\(двухраструбная\)', '', result)
    result = re.sub(r'\(ремонтная\)', '', result)
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
    # Убираем цвет "серый" (по умолчанию)
    result = re.sub(r'\bсерый\b', '', result)
    # Нормализуем размеры: 110х50 → 110 50
    result = re.sub(r'(\d+)[хx](\d+)', r'\1 \2', result)
    # Убираем Jk/Jakko - весь каталог Jakko, не нужно для сравнения
    result = re.sub(r'\bjk\b', '', result)
    result = re.sub(r'\bjakko\b', '', result)
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
