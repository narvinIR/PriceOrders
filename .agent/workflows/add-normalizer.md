---
description: Добавление правил нормализации в normalizers.py
---

# Добавление правил нормализации

## Структура normalizers.py

```
backend/utils/normalizers.py
├── _load_json_config()          # Загрузка JSON конфигов
├── expand_synonyms()            # Замена сокращений
├── normalize_sku()              # Нормализация артикула
├── extract_sku_from_text()      # Извлечение артикула
├── normalize_name()             # Основная нормализация (200+ правил)
├── extract_pipe_size()          # Размеры труб
├── extract_thread_size()        # Размеры резьбы
├── extract_fitting_size()       # Размеры фитингов
├── is_coupling_detachable()     # Американка или обычная муфта
└── is_reducer()                 # Переходник или нет
```

---

## Типы правил

### 1. Синонимы материалов

**Файл:** `backend/config/synonyms.json`

```json
{
  "material": {
    "пп": "полипропилен",
    "ппр": "полипропилен",
    "пнд": "компрессионный"
  }
}
```

### 2. Синонимы типов товаров

**Файл:** `backend/config/synonyms.json`

```json
{
  "product": {
    "колено": "отвод",
    "угольник": "отвод",
    "угол": "отвод"
  }
}
```

### 3. Regex правила в normalize_name()

```python
# Удаление упаковки
text = re.sub(r'\(уп\.?\s*\d+\s*шт\.?\)', '', text)

# Конвертация размера хомута
text = re.sub(r'хомут\s+(\d+)', convert_clamp_mm_to_inch, text)
```

---

## Пошаговое добавление правила

### Шаг 1: Определить паттерн

Пример: клиент пишет `"ПЭ труба"` вместо `"полиэтилен труба"`

### Шаг 2: Добавить в synonyms.json

```json
{
  "material": {
    "пэ": "полиэтилен"
  }
}
```

### Шаг 3: Добавить тест

```python
# tests/test_normalizers.py

def test_pe_synonym():
    result = normalize_name("ПЭ труба 32")
    assert "полиэтилен" in result
```

### Шаг 4: Запустить тесты

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_normalizers.py -v
```

---

## Примеры правил

### Удаление шума

```python
# Удалить цвет
text = re.sub(r'\b(серый|белый|серая|белая)\b', '', text)

# Удалить толщину стенки
text = re.sub(r'\([\d.]+\)', '', text)  # (2.2), (2.7)
```

### Конвертация

```python
# мм → дюймы для хомутов
CLAMP_MM_TO_INCH = {
    110: '4"',
    160: '6"'
}

def convert_clamp_mm_to_inch(match):
    mm = int(match.group(1))
    return f'хомут {CLAMP_MM_TO_INCH.get(mm, match.group(0))}'
```

### Стандартизация формата

```python
# pn20, pn-20, pn 20 → pn20
text = re.sub(r'pn[\s-]?(\d+)', r'pn\1', text, flags=re.IGNORECASE)
```

---

## Отладка нормализации

### Интерактивно

```python
from backend.utils.normalizers import normalize_name

# До
print(normalize_name("Труба ПП 110-3000 (2.7) серая (уп 10шт) Jakko"))

# После добавления правила
print(normalize_name("Новый тестовый кейс"))
```

### В тестах

```bash
PYTHONPATH=. pytest tests/test_normalizers.py::test_specific_case -v -s
```

---

## Checklist нового правила

- [ ] Добавлено в `synonyms.json` или `normalize_name()`
- [ ] Написан тест в `test_normalizers.py`
- [ ] Все тесты проходят
- [ ] Проверено на реальных данных клиента
- [ ] Закоммичено с описательным сообщением
