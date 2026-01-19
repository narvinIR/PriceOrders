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

## 🚀 Deploys & Commands

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
