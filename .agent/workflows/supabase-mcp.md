---
description: Работа с Supabase через MCP (миграции, SQL, логи)
---

# Supabase MCP Workflow

## Настройка

Для работы с Supabase MCP требуется правильная конфигурация в `mcp_config.json`.

1. **Access Token:**
   - Для **Management API** (создание проектов, apply_migration для DDL) нужен **Personal Access Token (PAT)**.
   - Сгенерировать: https://supabase.com/dashboard/account/tokens
   - Service Role JWT **НЕ ПОДХОДИТ** для Management операций, но работает для `execute_sql` (DML).

2. **Project Ref:**
   - ID проекта из URL (например, `cyfmvsxqswbkazgckxbs`)

```json
"supabase-priceorders": {
  "command": "npx",
  "args": [
    "-y",
    "@supabase/mcp-server-supabase@latest",
    "--access-token", "sbp_...",
    "--project-ref", "cyfmvsxqswbkazgckxbs"
  ]
}
```

## Основные операции

### 1. Выполнение SQL (DML)

Для SELECT, INSERT, UPDATE.

```python
mcp_supabase-priceorders_execute_sql(query="SELECT * FROM products LIMIT 5")
```

### 2. Применение миграций (DDL)

Для CREATE TABLE, ALTER, CREATE INDEX. Требует PAT.

```python
mcp_supabase-priceorders_apply_migration(
    name="add_vector_search",
    query="create extension vector;"
)
```

> **Важно:** Если миграция сложная или требует прав superuser (которых нет у PAT), лучше выполнить её через SQL Editor в Dashboard.

### 3. Просмотр логов

```python
mcp_supabase-priceorders_get_logs(service="postgres")
```

---

## Troubleshooting

- **401 Unauthorized**: Проверьте PAT токен. Если используете JWT, многие функции будут недоступны.
- **Privileges Error**: Пользователь токена не имеет прав. Используйте SQL Editor.
