# PriceOrders - Инструкции для Claude

## Проект

**PriceOrders** - система сопоставления товаров клиента с каталогом поставщика Jakko.
Автоматическое сопоставление артикулов и названий с учётом упаковок.

## Стек технологий

- **Backend:** Python 3.11 + FastAPI
- **Frontend:** Streamlit
- **База данных:** Supabase (PostgreSQL)
- **Библиотеки:** fuzzywuzzy, pandas, openpyxl, pydantic-settings

## Архитектура

```
backend/
├── config.py            # Настройки (пороги matching)
├── models/
│   ├── database.py      # Supabase клиент
│   └── schemas.py       # Pydantic модели
├── services/
│   ├── matching.py      # 6-уровневый алгоритм маппинга
│   └── excel.py         # Парсинг Excel (Jakko формат)
├── routers/
│   ├── orders.py        # API заказов
│   └── products.py      # API каталога
└── utils/
    └── normalizers.py   # Нормализация SKU и названий
```

## Ключевые концепции

### 6-уровневый алгоритм matching

1. **Точное SKU** (100%) - прямое совпадение артикула
2. **Точное название** (95%) - полное совпадение после нормализации
3. **Кэшированный маппинг** (100%) - сохранённые подтверждённые связи
4. **Fuzzy SKU** (90%) - Levenshtein distance ≤ 1
5. **Fuzzy название** (80%) - token_sort_ratio + token_set_ratio
6. **Не найдено** (0%) - требует ручной проверки

### Нормализация названий

Удаляется:
- Упаковка: `(уп 20 шт)`, `(20 шт)`
- Толщина: `(2.7)`, `(2.2)`
- Бренд: `Jk`, `Jakko`
- Цвет: `серый`

Конвертируется:
- `переход` → `переходник`
- `компенсатор кан` → `патрубок компенсационный`
- `хомут 110` → `хомут в комплекте 4"` (мм → дюймы)

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
pytest backend/tests/
```

## Важные файлы для изменений matching

При улучшении алгоритма сопоставления:
- [normalizers.py](backend/utils/normalizers.py) - добавить правила нормализации
- [matching.py](backend/services/matching.py) - изменить логику matching
- [config.py](backend/config.py) - настроить пороги confidence

## Данные

- **Каталог Jakko:** ~1500 товаров, категории 1-12
- **Формат прайса:** Excel с листами по категориям
- **Клиентские заказы:** Excel с артикулом, названием, количеством

## MCP Memory

Контекст проекта сохранён в MCP memory:
- `PriceOrders_MVP_Complete` - статус реализации
- `PriceOrders_Matching_Algorithm` - алгоритм matching
- `PriceOrders_Normalizers` - правила нормализации
- `PriceOrders_PackQty` - логика упаковок
- `PriceOrders_Config` - настройки порогов
