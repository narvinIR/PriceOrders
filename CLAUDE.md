# PriceOrders - Инструкции для Claude

## Проект

**PriceOrders** - система сопоставления товаров клиента с каталогом поставщика Jakko.
Автоматическое сопоставление артикулов и названий с учётом упаковок.

## Стек технологий

- **Backend:** Python 3.11 + FastAPI
- **Frontend:** Streamlit
- **База данных:** Supabase (PostgreSQL)
- **ML:** sentence-transformers, FAISS (semantic search)
- **Библиотеки:** fuzzywuzzy, pandas, openpyxl, pydantic-settings

## Архитектура

```
backend/
├── config.py            # Настройки (пороги matching)
├── main.py              # FastAPI приложение
├── models/
│   ├── database.py      # Supabase клиент
│   └── schemas.py       # Pydantic модели
├── services/
│   ├── matching.py      # 7-уровневый алгоритм маппинга
│   ├── embeddings.py    # ML semantic search (FAISS)
│   └── excel.py         # Парсинг Excel (Jakko формат)
├── routers/
│   ├── orders.py        # API заказов
│   ├── products.py      # API каталога
│   ├── clients.py       # API клиентов
│   └── analytics.py     # API статистики matching
└── utils/
    └── normalizers.py   # Нормализация SKU и названий

tests/
├── conftest.py          # Pytest fixtures
├── test_normalizers.py  # 47 unit тестов
├── test_matching_unit.py # 18 unit тестов
└── test_matching_full.py # 263 интеграционных теста
```

## Ключевые концепции

### 7-уровневый алгоритм matching

1. **Точное SKU** (100%) - прямое совпадение артикула
2. **Точное название** (95%) - полное совпадение после нормализации
3. **Кэшированный маппинг** (100%) - сохранённые подтверждённые связи
4. **Fuzzy SKU** (90%) - Levenshtein distance ≤ 1
5. **Fuzzy название** (80%) - token_sort_ratio + token_set_ratio + точный размер
6. **Semantic embedding** (≤75%) - ML поиск через FAISS
7. **Не найдено** (0%) - требует ручной проверки

### Нормализация названий

Удаляется:
- Упаковка: `(уп 20 шт)`, `(20 шт)`
- Толщина: `(2.7)`, `(2.2)`
- Бренд: `Jk`, `Jakko`, `Prestige`
- Цвет: `серый`

Конвертируется:
- `переход` → `переходник`
- `колено/угол/угольник` → `отвод`
- `ПП/ППР` → `полипропилен`
- `ПЭ/PERT` → `полиэтилен`
- `вн.рез/в/р` → `внутренняя резьба`
- `нар.рез/н/р` → `наружная резьба`
- `хомут 110` → `хомут в комплекте 4"` (мм → дюймы)
- `PN 20/PN-20/PN20` → `pn20`

### Точный matching размеров

Для труб извлекается размер (диаметр×длина):
- `extract_pipe_size("Труба 110×2000")` → `(110, 2000)`
- При fuzzy matching товары с другим размером пропускаются
- 110×2000 НЕ совпадёт с 110×3000

### pack_qty (упаковки)

- Читается из колонок Excel: ПАКЕТ, УПАКОВКА
- Fallback: парсинг из названия товара
- Заказ округляется вверх до целых упаковок

## Команды

```bash
# Backend
cd backend && uvicorn main:app --reload --port 8000

# Frontend
cd frontend && streamlit run app.py --server.port 3000

# Тесты
PYTHONPATH=. pytest tests/ -v

# Только unit тесты
PYTHONPATH=. pytest tests/test_normalizers.py tests/test_matching_unit.py -v

# Полный тест на реальных данных
PYTHONPATH=. python tests/test_matching_full.py
```

## API Эндпоинты

### Analytics API

- `GET /analytics/matching/stats` - статистика по уровням matching
- `POST /analytics/matching/stats/reset` - сброс статистики
- `GET /analytics/matching/levels` - описание алгоритма

Пример ответа `/matching/stats`:
```json
{
  "total": 263,
  "exact_sku": 222,
  "exact_name": 41,
  "fuzzy_name": 0,
  "not_found": 0,
  "avg_confidence": 98.4,
  "success_rate": 100.0
}
```

## Важные файлы для изменений matching

При улучшении алгоритма сопоставления:
- [normalizers.py](backend/utils/normalizers.py) - добавить правила нормализации
- [matching.py](backend/services/matching.py) - изменить логику matching
- [embeddings.py](backend/services/embeddings.py) - ML semantic search
- [config.py](backend/config.py) - настроить пороги confidence

## Данные

- **Каталог Jakko:** ~840 товаров, 12 категорий
- **Формат прайса:** Excel с листами по категориям
- **Клиентские заказы:** Excel с артикулом, названием, количеством

## MCP Memory

Контекст проекта сохранён в MCP memory:
- `PriceOrders_MVP_Complete` - статус реализации
- `PriceOrders_Matching_Algorithm` - алгоритм matching (v2.0)
- `PriceOrders_Normalizers` - правила нормализации
- `PriceOrders_PackQty` - логика упаковок
- `PriceOrders_Config` - настройки порогов
- `PriceOrders_Tests` - тестирование (328 тестов)
- `PriceOrders_Analytics_API` - API статистики
