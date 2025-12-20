"""
Telegram бот PriceOrders - сопоставление артикулов B2B.
"""
import sys
import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI
import uvicorn

sys.path.insert(0, '/home/dimas/projects/PriceOrders')

from bot.config import (
    BOT_TOKEN, WEBHOOK_MODE, WEBHOOK_URL, WEBHOOK_PATH, HOST, PORT
)
from bot.handlers import start, search, upload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot и Dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Регистрация роутеров
dp.include_router(start.router)
dp.include_router(search.router)
dp.include_router(upload.router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle для FastAPI"""
    if WEBHOOK_MODE:
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook установлен: {webhook_url}")
    yield
    if WEBHOOK_MODE:
        await bot.delete_webhook()
    await bot.session.close()


# FastAPI для webhook + health check
app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "priceorders-bot"}


@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict):
    """Обработка webhook от Telegram"""
    from aiogram.types import Update
    telegram_update = Update.model_validate(update, context={"bot": bot})
    await dp.feed_update(bot, telegram_update)
    return {"ok": True}


async def main():
    """Запуск бота в polling режиме (для разработки)"""
    logger.info("Запуск бота в polling режиме...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if WEBHOOK_MODE:
        uvicorn.run(app, host=HOST, port=PORT)
    else:
        asyncio.run(main())
