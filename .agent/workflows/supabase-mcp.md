---
description: Работа с Supabase через MCP (execute_sql, apply_migration, list_tables)
---

# MCP Supabase — Workflow

## Доступные MCP серверы

| MCP Server             | Project     | Ref                    |
| ---------------------- | ----------- | ---------------------- |
| `supabase-priceorders` | PriceOrders | `cyfmvsxqswbkazgckxbs` |
| `supabase-unify`       | Unify       | `eaubnaglbyklfntketng` |

---

## Основные инструменты

### 1. Информация о проекте

```
mcp_supabase-priceorders_get_project_url()
mcp_supabase-priceorders_list_tables(schemas: ["public"])
mcp_supabase-priceorders_list_migrations()
mcp_supabase-priceorders_list_extensions()
```

### 2. Выполнение SQL (SELECT, INSERT, UPDATE, DELETE)

```
mcp_supabase-priceorders_execute_sql(query: "SELECT * FROM products LIMIT 5")
```

> ⚠️ НЕ использовать для DDL (CREATE, ALTER, DROP) — для этого apply_migration!

### 3. Миграции (DDL)

```
mcp_supabase-priceorders_apply_migration(
  name: "add_column_to_products",
  query: "ALTER TABLE products ADD COLUMN new_field TEXT;"
)
```

### 4. Edge Functions

```
mcp_supabase-priceorders_list_edge_functions()
mcp_supabase-priceorders_get_edge_function(function_slug: "my-function")
mcp_supabase-priceorders_deploy_edge_function(name: "my-function", files: [...])
```

### 5. Storage

```
mcp_supabase-priceorders_list_storage_buckets()
mcp_supabase-priceorders_get_storage_config()
```

### 6. Логи и отладка

```
mcp_supabase-priceorders_get_logs(service: "postgres")  # postgres, auth, storage, edge-function
mcp_supabase-priceorders_get_advisors(type: "security")  # security, performance
```

### 7. Документация

```
mcp_supabase-priceorders_search_docs(graphql_query: '{ searchDocs(query: "RLS policies", limit: 5) { nodes { title href content } } }')
```

---

## Настройка нового MCP сервера

1. Получить PAT токен: Supabase Dashboard → Account → Access Tokens
2. Добавить в `~/.gemini/antigravity/mcp_config.json`:

```json
"supabase-projectname": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "-y", "@supabase/mcp-server-supabase@latest",
    "--access-token", "sbp_YOUR_PAT_TOKEN",
    "--project-ref", "YOUR_PROJECT_REF",
    "--features=account,database,debugging,development,functions,branching,storage,docs"
  ]
}
```

3. Перезагрузить Antigravity (Ctrl+Shift+P → Reload Window)

---

## Типичные сценарии

### Проверить структуру таблицы

// turbo

```
mcp_supabase-priceorders_execute_sql(query: "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'products'")
```

### Добавить индекс

```
mcp_supabase-priceorders_apply_migration(name: "add_products_sku_idx", query: "CREATE INDEX idx_products_sku ON products(sku);")
```

### Проверить RLS политики

```
mcp_supabase-priceorders_get_advisors(type: "security")
```
