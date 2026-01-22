---
description: Отладка алгоритма matching (7 уровней, фильтры, нормализация)
---

# Отладка Matching алгоритма

## Архитектура matching

```
1. Точное SKU (100%)         → sku == catalog_sku
2. Точное название (95%)     → normalized_name == catalog_name
3. Кэшированный маппинг      → mappings table lookup
4. Fuzzy SKU (90%)           → Levenshtein ≤ 1
5. Fuzzy название (80%)      → fuzzywuzzy + фильтры
6. LLM matching (≤75%)       → OpenRouter API (Grok-4.1-fast)
7. Не найдено (0%)           → требует ручной проверки
```

---

## Пошаговая отладка

### 1. Проверить нормализацию

```python
from backend.utils.normalizers import normalize_name, normalize_sku

# Проверить нормализацию
print(normalize_name("Труба ПП 110-3000 (2.2) серая (уп 10шт)"))
# Ожидаемый результат: "труба полипропилен 110 3000"

print(normalize_sku("202051110R"))
# Ожидаемый результат: "202051110r"
```

### 2. Проверить извлечение типа

```python
from backend.utils.matching_helpers import extract_product_type

print(extract_product_type("Труба канализационная 110"))
# → "труба"

print(extract_product_type("Отвод 45° 110"))
# → "отвод"
```

### 3. Тестировать match_item

```python
from backend.services.matching import MatchingService

matcher = MatchingService()
result = matcher.match_item(
    client_id=None,
    client_sku="",
    client_name="Труба ПП 110-3000 серая"
)

print(f"Product: {result.product_name}")
print(f"Confidence: {result.confidence}%")
print(f"Match type: {result.match_type}")
```

### 4. Проверить фильтры

```python
from backend.utils.matching_helpers import (
    extract_product_type,
    extract_angle,
    extract_thread_type,
    detect_client_category
)

name = "Отвод ПП 110 45° в/р"

print(f"Type: {extract_product_type(name)}")
print(f"Angle: {extract_angle(name)}")
print(f"Thread: {extract_thread_type(name)}")
print(f"Category: {detect_client_category(name)}")
```

---

## Логирование

### Включить debug логирование

```python
import logging
logging.getLogger("backend.services.matching").setLevel(logging.DEBUG)
```

### Логи в продакшене

```bash
northflank get service logs --tail --projectId jakko --serviceId priceorders-bot | grep -E "(match_item|confidence|match_type)"
```

---

## Частые проблемы

### Неверный тип товара

**Симптом:** Труба матчится на отвод

**Решение:** Добавить правило в `extract_product_type()`:

```python
# backend/utils/matching_helpers.py
if "труба" in name_lower:
    return "труба"
```

### Неверный размер

**Симптом:** 110×2000 матчится на 110×3000

**Решение:** Проверить `extract_pipe_size()`:

```python
from backend.utils.normalizers import extract_pipe_size

print(extract_pipe_size("Труба ПП 110×2000"))
# Должно вернуть (110, 2000)
```

### Низкий confidence при правильном товаре

**Симптом:** Товар найден, но confidence < 80%

**Решение:** Проверить fuzzy matching threshold в `config.py`:

```python
# backend/config.py
FUZZY_THRESHOLD = 75  # Минимальный порог для fuzzy match
```

---

## Инструменты отладки

### Скрипт тестирования

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 scripts/test_elf_matching.py
```

### Интерактивный REPL

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 -i -c "from backend.services.matching import MatchingService; m = MatchingService()"
```

Теперь можно вызывать:

```python
>>> m.match_item(None, "", "Труба ПП 110-3000")
```
