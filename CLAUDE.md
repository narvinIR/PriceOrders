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
│   ├── llm_matcher.py   # LLM matching через OpenRouter API
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
├── conftest.py              # Pytest fixtures
├── test_normalizers.py      # unit тесты нормализации
├── test_matching_unit.py    # unit тесты matching
├── test_bot_matching.py     # тесты бота
├── test_category_preference.py # тесты категорий
└── test_e2e_matching.py     # 51 E2E тест (парсинг + matching)
```

## Ключевые концепции

### 7-уровневый алгоритм matching (v3.1)

1. **Точное SKU** (100%) - прямое совпадение артикула
2. **Точное название** (95%) - полное совпадение после нормализации
3. **Кэшированный маппинг** (100%) - сохранённые подтверждённые связи
4. **Fuzzy SKU** (90%) - Levenshtein distance ≤ 1
5. **Fuzzy название** (80%) - с фильтрами по типу, углу, категории
6. **LLM matching** (≤75%) - OpenRouter API (Grok 4.1 fast)
7. **Не найдено** (0%) - требует ручной проверки

### LLM Matching (v3.1)

LLM matching через OpenRouter API заменяет локальный ML (экономит ~500 МБ RAM).

**Промпт хранится в Supabase:**
- Таблица: `settings`
- Ключ: `llm_system_prompt`
- Кэширование: 10 минут
- Fallback: `DEFAULT_SYSTEM_PROMPT` в коде

**Редактирование промпта:**
```sql
UPDATE settings SET value = '...' WHERE key = 'llm_system_prompt';
```

### Фильтры matching (v3.0)

Применяются ДО выбора лучшего совпадения:
- **extract_product_type** - тип: труба, отвод, тройник, муфта, заглушка...
- **extract_angle** - угол: 45°, 67°, 87°, 90°
- **extract_thread_type** - резьба: вн (в/р), нар (н/р)
- **detect_client_category** - категория: sewer, prestige, outdoor, ppr
- **clamp_fits_mm** - размер хомута по диапазону мм

### Нормализация названий

Удаляется:
- Упаковка: `(уп 20 шт)`, `(20 шт)`
- Толщина: `(2.7)`, `(2.2)`
- Бренд: `Jk`, `Jakko` (НО НЕ Prestige!)
- Цвет: `серый`, `белый`

Конвертируется:
- `переход` → `переходник`
- `колено/угол/угольник` → `отвод`
- `ПП/ППР` → `полипропилен`
- `ПЭ/PERT` → `полиэтилен`
- `вн.рез/в/р` → `внутренняя резьба`
- `нар.рез/н/р` → `наружная резьба`
- `хомут 110` → `хомут в комплекте 4"` (мм → дюймы)
- `PN 20/PN-20/PN20` → `pn20`
- `малошумн*` → `prestige` (линейка малошумной канализации)

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
- `PriceOrders_Matching_Algorithm` - алгоритм matching (v3.0)
- `PriceOrders_Normalizers` - правила нормализации
- `PriceOrders_PackQty` - логика упаковок
- `PriceOrders_Config` - настройки порогов
- `PriceOrders_Tests` - тестирование (121 тест, все проходят)
- `PriceOrders_Analytics_API` - API статистики

## Telegram Bot

Бот для B2B клиентов:
- Отправь список артикулов → получи Excel с результатом
- Формат: `название количество` (каждый с новой строки)
- Пример: `Труба ПП 110×3000 серая 5`

Запуск: `PYTHONPATH=. python3 bot/main.py`
