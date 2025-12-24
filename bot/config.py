"""
Конфигурация Telegram бота PriceOrders.
Паттерны из VlessReality: валидация обязательных переменных.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# === Telegram (обязательные) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

ADMIN_ID_STR = os.getenv("ADMIN_ID")
if not ADMIN_ID_STR:
    raise ValueError("ADMIN_ID environment variable is required")
ADMIN_ID = int(ADMIN_ID_STR)

logger.info(f"✅ Bot config loaded: ADMIN_ID={ADMIN_ID}")

# === Supabase (обязательные) ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("⚠️ Supabase credentials not set - database features disabled")

# Режим работы (default=true для Northflank)
WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "true").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://jakko--priceorders-bot--kbhsjrb6n8tm.code.run")
WEBHOOK_PATH = "/webhook/telegram"

# Сервер
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Matching
CONFIDENCE_THRESHOLD = 95.0  # Автоматическое подтверждение при >= 95%
