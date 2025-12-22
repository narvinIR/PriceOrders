"""
Telegram бот PriceOrders - сопоставление артикулов B2B.
Паттерны из VlessReality: lifecycle hooks, bot commands.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from collections import OrderedDict

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from fastapi import FastAPI, BackgroundTasks
import uvicorn

from bot.config import (
    BOT_TOKEN, WEBHOOK_MODE, WEBHOOK_URL, WEBHOOK_PATH, HOST, PORT
)
from bot.handlers import start, search, upload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Дедупликация webhook запросов (update_id → timestamp)
# Telegram повторяет webhook если не получает 200 OK быстро
_processed_updates: OrderedDict[int, float] = OrderedDict()
_MAX_CACHE_SIZE = 1000
_UPDATE_TTL = 300  # 5 минут

# Bot и Dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Регистрация роутеров (порядок важен!)
# Команды должны быть ПЕРВЫМИ, текстовые сообщения ПОСЛЕДНИМИ
dp.include_router(start.router)   # /start, /help, /stats
dp.include_router(search.router)  # /search + callbacks
dp.include_router(upload.router)  # F.document + F.text (последний!)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("🚀 Bot is starting...")

    # Регистрация команд в меню Telegram
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="search", description="🔍 Поиск товара"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="stats", description="📊 Статистика (admin)"),
    ])

    logger.info("✅ Bot commands registered")
    logger.info("✅ Bot started successfully!")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("🛑 Bot is shutting down...")
    await bot.session.close()
    logger.info("✅ Bot stopped")


# Регистрация lifecycle hooks
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


def _warmup_matcher():
    """Синхронный прогрев для запуска в потоке (не блокирует event loop)"""
    import time
    from bot.handlers.upload import get_matcher

    start = time.time()
    logger.info("⏳ Загрузка MatchingService...")
    matcher = get_matcher()
    logger.info(f"✅ MatchingService создан за {time.time()-start:.1f}s")

    start = time.time()
    logger.info("⏳ Прогрев match_item (загрузка ML модели)...")
    matcher.match_item(None, "test", "test")
    logger.info(f"✅ match_item готов за {time.time()-start:.1f}s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle для FastAPI"""
    # Прогрев ML модели ДО приёма запросов (иначе webhook таймаутит)
    logger.info("🔥 Прогрев MatchingService...")
    try:
        # Прогрев в отдельном потоке (не блокирует event loop)
        await asyncio.wait_for(
            asyncio.to_thread(_warmup_matcher),
            timeout=120.0  # 2 минуты на прогрев
        )
        logger.info("✅ MatchingService полностью готов")
    except asyncio.TimeoutError:
        logger.error("❌ Таймаут прогрева ML модели (120 сек)")
    except Exception as e:
        logger.error(f"❌ Ошибка прогрева: {e}", exc_info=True)

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


def _cleanup_old_updates():
    """Очистка старых update_id из кэша"""
    now = time.time()
    while _processed_updates:
        oldest_id, oldest_time = next(iter(_processed_updates.items()))
        if now - oldest_time > _UPDATE_TTL:
            _processed_updates.pop(oldest_id)
        else:
            break
    # Лимит размера кэша
    while len(_processed_updates) > _MAX_CACHE_SIZE:
        _processed_updates.popitem(last=False)


async def _process_update_background(update: dict):
    """Фоновая обработка update (не блокирует webhook response)"""
    from aiogram.types import Update
    try:
        telegram_update = Update.model_validate(update, context={"bot": bot})
        await dp.feed_update(bot, telegram_update)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки update: {e}", exc_info=True)


@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict, background_tasks: BackgroundTasks):
    """
    Обработка webhook от Telegram.

    ВАЖНО: Возвращаем 200 OK СРАЗУ, обработка в фоне.
    Это предотвращает повторные запросы от Telegram при долгой обработке.
    """
    update_id = update.get("update_id")

    # Дедупликация - игнорируем уже обработанные update_id
    if update_id in _processed_updates:
        logger.warning(f"⚠️ Дубликат update_id={update_id}, игнорирую")
        return {"ok": True}

    # Помечаем как обрабатываемый ДО начала обработки
    _processed_updates[update_id] = time.time()
    _cleanup_old_updates()

    logger.info(f"📨 Webhook update_id={update_id}")

    # Обработка в фоне - webhook возвращает 200 OK сразу
    background_tasks.add_task(_process_update_background, update)

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
