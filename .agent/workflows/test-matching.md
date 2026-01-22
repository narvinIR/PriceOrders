---
description: Запуск тестов matching (unit, e2e, полный прогон)
---

# Тестирование Matching

## Быстрый запуск

### Все тесты

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/ -v
```

---

## Категории тестов

### Unit тесты нормализации

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_normalizers.py -v
```

Тестируют:

- `normalize_name()` — удаление упаковок, толщины, бренда
- `normalize_sku()` — lowercase, пробелы
- `extract_pipe_size()` — парсинг размеров труб

### Unit тесты matching

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_matching_unit.py -v
```

Тестируют:

- Фильтры по типу товара
- Фильтры по углу отвода
- Извлечение резьбы

### Тесты бота

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_bot_matching.py -v
```

Тестируют:

- Парсинг текстовых списков
- Обработка Excel файлов

### E2E тесты (51 тест)

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_e2e_matching.py -v
```

Тестируют полный цикл:

- Парсинг клиентского заказа
- Matching с каталогом
- Генерация Excel результата

---

## Полный прогон на реальных данных

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 tests/test_matching_full.py
```

Этот скрипт:

1. Загружает реальный каталог из Supabase
2. Прогоняет тестовые заказы
3. Выводит статистику matching

---

## Запуск конкретного теста

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/test_matching_unit.py::test_extract_angle -v
```

## Тесты с покрытием

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. pytest tests/ --cov=backend --cov-report=html
```

Отчёт: `htmlcov/index.html`

---

## Fixtures (conftest.py)

### Доступные fixtures

```python
@pytest.fixture
def matcher():
    """Инстанс MatchingService"""
    return MatchingService()

@pytest.fixture
def sample_products():
    """Тестовый каталог товаров"""
    return [...]
```

---

## Добавление нового теста

### 1. Добавить в соответствующий файл

```python
# tests/test_matching_unit.py

def test_new_filter_case(matcher):
    result = matcher.match_item(None, "", "Новый тестовый кейс")
    assert result.confidence >= 80
    assert "ожидаемое" in result.product_name.lower()
```

### 2. Запустить новый тест

```bash
PYTHONPATH=. pytest tests/test_matching_unit.py::test_new_filter_case -v
```

---

## CI/CD интеграция

Тесты запускаются автоматически в GitHub Actions при push:

```yaml
# .github/workflows/tests.yml
- name: Run tests
  run: PYTHONPATH=. pytest tests/ -v
```
