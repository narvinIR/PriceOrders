---
description: Импорт маппингов клиента в Supabase (Эльф, новые клиенты)
---

# Импорт маппингов клиента

## Существующие клиенты

### Эльф

**Client ID:** `5013baff-4e85-448c-a8af-a90594407e43`

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 scripts/import_elf_mappings.py
```

Проверка после импорта:

// turbo

```bash
cd /home/dimas/projects/PriceOrders && PYTHONPATH=. python3 scripts/test_elf_matching.py
```

---

## Добавление нового клиента

### 1. Создать клиента в БД

```sql
INSERT INTO clients (name, email, phone)
VALUES ('Новый клиент', 'client@example.com', '+7...')
RETURNING id;
```

Или через MCP:

```
mcp_supabase-priceorders_execute_sql(query: "INSERT INTO clients (name) VALUES ('Новый клиент') RETURNING id")
```

### 2. Создать скрипт импорта

```python
# scripts/import_newclient_mappings.py

import os
from uuid import UUID
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
CLIENT_ID = UUID("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

# Маппинги: client_sku → product_id
MAPPINGS = {
    "ClientSKU001": "product-uuid-1",
    "ClientSKU002": "product-uuid-2",
}

def main():
    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    for client_sku, product_id in MAPPINGS.items():
        db.table("mappings").upsert({
            "client_id": str(CLIENT_ID),
            "client_sku": client_sku,
            "product_id": product_id,
            "confidence": 100,
            "match_type": "manual",
            "verified": True
        }, on_conflict="client_id,client_sku").execute()

    print(f"Imported {len(MAPPINGS)} mappings")

if __name__ == "__main__":
    main()
```

### 3. Запустить импорт

```bash
PYTHONPATH=. python3 scripts/import_newclient_mappings.py
```

---

## Формат таблицы mappings

| Поле         | Тип       | Описание                                  |
| ------------ | --------- | ----------------------------------------- |
| `id`         | UUID      | Primary key                               |
| `client_id`  | UUID      | FK → clients                              |
| `client_sku` | TEXT      | Артикул клиента                           |
| `product_id` | UUID      | FK → products                             |
| `confidence` | FLOAT     | 0-100                                     |
| `match_type` | TEXT      | exact_sku, exact_name, fuzzy, llm, manual |
| `verified`   | BOOL      | Подтверждён оператором                    |
| `created_at` | TIMESTAMP | Дата создания                             |

---

## Проверка маппингов

### Подсчёт маппингов клиента

```sql
SELECT COUNT(*) FROM mappings WHERE client_id = 'CLIENT_UUID';
```

### Список маппингов

```sql
SELECT m.client_sku, p.name as product_name, m.confidence
FROM mappings m
JOIN products p ON m.product_id = p.id
WHERE m.client_id = 'CLIENT_UUID'
ORDER BY m.client_sku;
```

---

## Экспорт маппингов

### В CSV

```python
import csv
from backend.models.database import get_supabase_client

db = get_supabase_client()
result = db.table("mappings") \
    .select("client_sku, product_id, confidence") \
    .eq("client_id", "CLIENT_UUID") \
    .execute()

with open("mappings_export.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["client_sku", "product_id", "confidence"])
    writer.writeheader()
    writer.writerows(result.data)
```
