# PriceOrders - Antigravity Knowledge

**Проект:** Telegram бот для B2B сопоставления прайс-листов (Jakko)
**Путь:** `/home/dimas/projects/PriceOrders`

---

## 🛠 Технологии

| Компонент   | Технология            | Описание                             |
| ----------- | --------------------- | ------------------------------------ |
| **Backend** | Python 3.11, FastAPI  | API и логика бота                    |
| **Bot**     | aiogram 3.x           | Telegram интерфейс                   |
| **DB**      | Supabase (PostgreSQL) | Хранение товаров, маппингов, истории |
| **ML**      | sentence-transformers | Семантический поиск (Embeddings)     |
| **Deploy**  | Northflank            | Docker хостинг                       |

---

## �️ Database (Supabase)

**URL:** `https://cyfmvsxqswbkazgckxbs.supabase.co`

### Таблицы

- `products` (839 записей) — Каталог товаров Jakko + embeddings (векторный поиск)
- `clients` — Список клиентов (вкл. "Эльф")
- `mappings` (~305 записей) — Сохраненные связи: `client_sku` ↔ `product_id`
- `orders` — История загруженных файлов

> **Note:** Таблица `match_stats` не используется (статистика считается in-memory).

### Access

Для работы локальных скриптов (`scripts/`) требуется `.env` с ключами:

- `SUPABASE_SERVICE_ROLE_KEY` (JWT) — Полный доступ (bypass RLS)
- `SUPABASE_URL` — REST API endpoint
- `SUPABASE_ACCESS_TOKEN` (PAT) — Для MCP и Management API

### MCP (Antigravity)

**Server:** `supabase-priceorders`

```bash
# Основные инструменты
mcp_supabase-priceorders_list_tables(schemas: ["public"])
mcp_supabase-priceorders_execute_sql(query: "SELECT ...")

mcp_supabase-priceorders_apply_migration(name: "...", query: "ALTER ...")
```

**ML Search:**

- Имплементирован через `pgvector` + OpenAI embeddings
- Для работы нужен валидный `OPENROUTER_API_KEY` или `OPENAI_API_KEY`
- Скрипт генерации: `python3 scripts/generate_embeddings_openai.py`

> **Workflow:** [/supabase-mcp](.agent/workflows/supabase-mcp.md)

## �🚀 Deploys & Commands

### Northflank

- **Service:** `priceorders-bot`
- **Region:** Frankfurt
- **Deploy:** Auto-deploy on push to `main`
- **Logs:** `northflank get service logs --tail --projectId jakko --serviceId priceorders-bot`
- **Restart:** `curl -X POST .../restart` (для сброса кэша)

### Local Dev

- **Run Bot:** `PYTHONPATH=. python3 bot/main.py`
- **Import ELF:** `PYTHONPATH=. python3 scripts/import_elf_mappings.py`
- **Test ELF:** `PYTHONPATH=. python3 scripts/test_elf_matching.py`

### VS Code

- **Settings:** `.vscode/settings.json` (NF_TOKEN auto-load)
- **Extensions:**
  - `GrapeCity.gc-excelviewer` (для просмотра .xlsx отчетов)
  - `ms-python.python`

---

## 📂 Ключевые файлы

- `bot/handlers/upload.py` — Логика обработки файлов (Excel/Text/Photo)
- `backend/services/matching.py` — Алгоритм матчинга (7 уровней)
- `CLAUDE.md` — Детальная документация проекта
- `northflank.json` — Конфиг для деплоя

---

## 🧠 Memory Context

### Клиент "Эльф"

- **ID:** `5013baff-4e85-448c-a8af-a90594407e43`
- **Маппинги:** Импортируются скриптом, хранятся в БД
- **Статус:** 100% покрытие (81/81 товаров) на 19.01.2026

### Особенности

- Использует `client_id` для кэширования маппингов
- Большие заказы обрабатываются параллельно (`asyncio.to_thread`)
