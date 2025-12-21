"""
Обработчик интерактивного поиска товаров.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from uuid import uuid4

from bot.keyboards.inline import get_match_keyboard
from bot.handlers.upload import get_matcher

router = Router()

# Временное хранилище результатов поиска
_search_results = {}


@router.message(Command("search"))
async def cmd_search(message: Message):
    """Поиск товара по запросу"""
    # Извлекаем запрос после /search
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Укажите запрос после команды.\n\n"
            "<b>Пример:</b>\n"
            "<code>/search Труба ПП 110×2000</code>"
        )
        return

    query = parts[1].strip()
    await message.answer(f"🔍 Ищу: <b>{query}</b>...")

    try:
        matcher = get_matcher()
        # Используем client_id = telegram_id для кэширования
        client_id = str(message.from_user.id)

        result = matcher.match_item(
            client_id=client_id,
            client_sku=query,
            client_name=query
        )

        if result.match_type == 'not_found':
            await message.answer(
                f"❌ <b>Не найдено</b>\n\n"
                f"Запрос: <code>{query}</code>\n\n"
                f"Попробуйте уточнить запрос или проверьте написание."
            )
            return

        # Сохраняем результат для callback
        search_id = str(uuid4())[:8]
        _search_results[search_id] = {
            'client_id': client_id,
            'client_sku': query,
            'product_id': str(result.product_id),
            'product_sku': result.product_sku,
        }

        # Формируем ответ
        confidence_emoji = "✅" if result.confidence >= 95 else "⚠️" if result.confidence >= 75 else "❓"

        text = f"""
{confidence_emoji} <b>Найдено совпадение</b>

<b>Ваш запрос:</b>
<code>{query}</code>

<b>Товар Jakko:</b>
{result.product_name}

<b>Артикул:</b> <code>{result.product_sku}</code>
<b>Уверенность:</b> {result.confidence:.0f}%
<b>Метод:</b> {result.match_type}
"""

        if result.pack_qty and result.pack_qty > 1:
            text += f"\n<b>Упаковка:</b> {result.pack_qty} шт"

        keyboard = get_match_keyboard(search_id, result.needs_review)
        await message.answer(text, reply_markup=keyboard)

    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {e}")


@router.callback_query(F.data.startswith("confirm:"))
async def callback_confirm(callback: CallbackQuery):
    """Подтверждение соответствия"""
    search_id = callback.data.split(":")[1]

    if search_id not in _search_results:
        await callback.answer("⏰ Результат устарел, повторите поиск")
        return

    data = _search_results.pop(search_id)

    # TODO: Сохранить маппинг в Supabase
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Соответствие сохранено!</b>",
        reply_markup=None
    )
    await callback.answer("Сохранено!")


@router.callback_query(F.data.startswith("reject:"))
async def callback_reject(callback: CallbackQuery):
    """Отклонение соответствия"""
    search_id = callback.data.split(":")[1]
    _search_results.pop(search_id, None)

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Соответствие отклонено</b>",
        reply_markup=None
    )
    await callback.answer("Отклонено")
