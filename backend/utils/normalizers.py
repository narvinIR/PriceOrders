import re
import unicodedata

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
