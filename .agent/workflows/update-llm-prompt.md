---
description: Обновление LLM системного промпта в Supabase
---

# Обновление LLM промпта

## Где хранится промпт

**Таблица:** `settings`  
**Ключ:** `llm_system_prompt`  
**Кэширование:** 10 минут  
**Fallback:** `DEFAULT_SYSTEM_PROMPT` в коде

---

## Просмотр текущего промпта

### Через MCP

```
mcp_supabase-priceorders_execute_sql(query: "SELECT value FROM settings WHERE key = 'llm_system_prompt'")
```

### Через SQL

```sql
SELECT key, value, updated_at
FROM settings
WHERE key = 'llm_system_prompt';
```

---

## Обновление промпта

### Через MCP

```
mcp_supabase-priceorders_execute_sql(query: "UPDATE settings SET value = 'Новый промпт...', updated_at = NOW() WHERE key = 'llm_system_prompt'")
```

### Через SQL

```sql
UPDATE settings
SET value = $$
Ты помощник для сопоставления товаров.
Каталог: сантехника Jakko (трубы, фитинги, канализация).

Правила:
1. Учитывай тип товара (труба, отвод, муфта)
2. Учитывай размеры (диаметр, длина)
3. Учитывай материал (ПП, ПЭ)
4. Возвращай только ID товара или "NOT_FOUND"
$$,
updated_at = NOW()
WHERE key = 'llm_system_prompt';
```

---

## Структура эффективного промпта

```
Ты эксперт по сантехнике Jakko.

ЗАДАЧА: Сопоставить товар клиента с каталогом.

КАТАЛОГ содержит:
- Трубы ПП/ПЭ (диаметры 20-160мм)
- Фитинги (отводы, тройники, муфты)
- Канализация (110мм система)

ПРАВИЛА MATCHING:
1. Тип товара ДОЛЖЕН совпадать
2. Размеры ДОЛЖНЫ совпадать
3. При неопределённости вернуть NOT_FOUND

ФОРМАТ ОТВЕТА:
- Если найден: product_id (UUID)
- Если не найден: NOT_FOUND
```

---

## Тестирование изменений

### 1. Обновить промпт

```sql
UPDATE settings SET value = '...' WHERE key = 'llm_system_prompt';
```

### 2. Сбросить кэш бота

```bash
curl -s -X POST -H "Authorization: Bearer $NF_TOKEN" \
  "https://api.northflank.com/v1/projects/jakko/services/priceorders-bot/restart"
```

### 3. Отправить тестовый заказ в бота

Отправить сложный товар, который раньше не матчился.

### 4. Проверить логи

```bash
northflank get service logs --tail --projectId jakko --serviceId priceorders-bot | grep "LLM"
```

---

## Fallback промпт

Если таблица `settings` пуста, используется промпт из кода:

```python
# backend/services/llm_matcher.py

DEFAULT_SYSTEM_PROMPT = """
Ты помощник для сопоставления артикулов сантехники.
...
"""
```

---

## Мониторинг LLM

### Стоимость запросов

OpenRouter API (Grok-4.1-fast):

- ~$0.0001 за запрос
- Лимит: настроить в OpenRouter dashboard

### Логирование

```python
# В llm_matcher.py
logger.info(f"LLM request: {client_name}")
logger.info(f"LLM response: {response}")
```

---

## Troubleshooting

### LLM не вызывается

Проверить пороги в `config.py`:

```python
LLM_THRESHOLD = 60  # Минимальный confidence для fallback к LLM
```

### Неверные ответы LLM

1. Улучшить промпт с примерами
2. Добавить few-shot examples:

```
ПРИМЕРЫ:
Клиент: "Труба ПП 110-3000" → ID: abc-123
Клиент: "Отвод 45 110" → ID: def-456
```

### API ошибки

Проверить ключ:

```bash
echo $OPENROUTER_API_KEY
```

Проверить баланс: https://openrouter.ai/account
