"""
Обработчики /start и /help команд.
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from bot.config import ADMIN_ID

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение"""
    text = """
🛒 <b>Автоподбор товаров Jakko</b>

Отправь заявку — получи готовый заказ!

<b>Формат:</b> название количество
<b>Пример:</b>
<code>Труба ПП 110×2000 5
Отвод 45° 110 3</code>

📎 Или загрузи Excel файл
"""
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам"""
    text = """
<b>Команды бота:</b>

/start — начать работу
/search &lt;запрос&gt; — поиск товара
/help — эта справка

<b>Загрузка заказа:</b>
Отправь Excel файл (.xlsx) с колонками:
• Артикул (SKU)
• Название
• Количество

Бот найдёт соответствия в каталоге Jakko и вернёт результат.
"""
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика matching (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Команда доступна только администратору")
        return

    try:
        from bot.handlers.upload import get_matcher
        matcher = get_matcher()
        stats = matcher.get_stats()

        text = f"""
<b>Статистика matching:</b>

Всего: {stats['total']}
• exact_sku: {stats['exact_sku']}
• exact_name: {stats['exact_name']}
• cached_mapping: {stats['cached_mapping']}
• fuzzy_sku: {stats['fuzzy_sku']}
• fuzzy_name: {stats['fuzzy_name']}
• semantic: {stats['semantic_embedding']}
• not_found: {stats['not_found']}

Средний confidence: {stats['avg_confidence']:.1f}%
Success rate: {stats['success_rate']:.1f}%
"""
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# Fallback handler удалён - перехватывал все сообщения и мешал другим роутерам
# Теперь неизвестные сообщения просто игнорируются
