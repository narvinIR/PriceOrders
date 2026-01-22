---
description: Локальная разработка бота и API (запуск, тесты, отладка)
---

# Локальная разработка PriceOrders

## Запуск бота (polling режим)

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 bot/main.py
```

> **Note:** В polling режиме бот запускается локально и получает обновления через long-polling.

## Запуск FastAPI backend

// turbo

```bash
cd /home/dimas/projects/PriceOrders/backend && uvicorn main:app --reload --port 8000
```

## Проверка health endpoint

// turbo

```bash
curl http://localhost:8000/health
```

---

## IDE настройки

### VS Code Extensions

- `ms-python.python` — Python IntelliSense
- `GrapeCity.gc-excelviewer` — просмотр .xlsx файлов

### Переменные окружения

Требуется `.env` в корне проекта:

```env
SUPABASE_URL=https://cyfmvsxqswbkazgckxbs.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
BOT_TOKEN=123456:ABC...
OPENROUTER_API_KEY=sk-or-...
```

---

## Типичные задачи

### Тестирование изменений matching

1. Запустить бота локально
2. Отправить тестовый файл в Telegram
3. Проверить результат

### Отладка с логами

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 bot/main.py 2>&1 | tee bot.log
```

### Прогрев кэша вручную

```python
from backend.services.matching import MatchingService
matcher = MatchingService()
matcher.match_item(None, "test", "test")
```

---

## Troubleshooting

### "Module not found" ошибка

```bash
export PYTHONPATH=/home/dimas/projects/PriceOrders
```

### Telegram webhook конфликт

При переключении между локальным и production режимами удалить webhook:

```bash
curl "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook"
```
