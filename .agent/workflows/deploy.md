---
description: Деплой на Northflank (git push, мониторинг, рестарт)
---

# Деплой PriceOrders на Northflank

## Quick Deploy

// turbo-all

### 1. Коммит и пуш

```bash
cd /home/dimas/projects/PriceOrders && git add . && git commit -m "fix: description" && git push origin main
```

> **Auto-deploy:** Northflank автоматически билдит Docker образ при push в `main`.

---

## Мониторинг деплоя

### 2. Проверить статус сервиса

```bash
curl -s -H "Authorization: Bearer $NF_TOKEN" \
  "https://api.northflank.com/v1/projects/jakko/services/priceorders-bot" \
  | jq '{sha: .data.deployment.internal.deployedSHA[0:7], status: .data.status.deployment.status}'
```

### 3. Логи в реальном времени

```bash
northflank get service logs --tail --projectId jakko --serviceId priceorders-bot
```

### 4. Логи через API (последние 20)

```bash
curl -s -H "Authorization: Bearer $NF_TOKEN" \
  "https://api.northflank.com/v1/projects/jakko/services/priceorders-bot/logs?limit=20" \
  | jq '.data.logs[].message'
```

---

## Управление сервисом

### Рестарт (очистка кэша)

```bash
curl -s -X POST -H "Authorization: Bearer $NF_TOKEN" \
  "https://api.northflank.com/v1/projects/jakko/services/priceorders-bot/restart"
```

### SSH в pod

```bash
northflank exec service --projectId jakko --serviceId priceorders-bot
```

---

## Northflank Token

### Получение токена

1. Открыть https://app.northflank.com
2. Settings → API Tokens → Create Token
3. Сохранить в `~/.northflank/.env`:

```bash
export NF_TOKEN="nf-eyJhbGciOiJIUzI1NiIsInR5cCI..."
```

### Загрузка в VS Code

В `.vscode/settings.json` добавлено:

```json
{
  "terminal.integrated.env.linux": {
    "NF_TOKEN": "${env:NF_TOKEN}"
  }
}
```

---

## Troubleshooting

### Build failed

1. Проверить `Dockerfile` на синтаксис
2. Проверить `requirements.txt` на валидность
3. Смотреть логи билда в Northflank Dashboard

### Service unhealthy

1. Проверить `/health` endpoint
2. Проверить переменные окружения в Settings → Variables
3. Смотреть логи: `northflank get service logs --tail --projectId jakko --serviceId priceorders-bot`

### Webhook не получает сообщения

1. Проверить URL: `https://jakko--priceorders-bot--kbhsjrb6n8tm.code.run/webhook`
2. Проверить Telegram webhook info:

```bash
curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" | jq
```
