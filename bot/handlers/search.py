"""
Обработчик интерактивного поиска товаров.
"""
import time
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers.upload import get_matcher
from bot.keyboards.inline import get_match_keyboard

router = Router()

# Временное хранилище результатов поиска: {search_id: (data, timestamp)}
_search_results: dict[str, tuple[dict, float]] = {}
_SEARCH_TTL = 3600  # 1 час TTL


def _cleanup_search_results():
    """Удаляем устаревшие результаты поиска (TTL 1 час)"""
    now = time.time()
    expired = [k for k, (_, ts) in _search_results.items() if now - ts > _SEARCH_TTL]
    for k in expired:
        del _search_results[k]


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

        # Сохраняем результат для callback (full UUID + timestamp)
        _cleanup_search_results()  # Очищаем устаревшие
        search_id = str(uuid4())  # Full UUID (не [:8] - избегаем коллизий)
        _search_results[search_id] = ({
            'client_id': client_id,
            'client_sku': query,
            'product_id': str(result.product_id),
            'product_sku': result.product_sku,
        }, time.time())

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

    # Атомарный pop() вместо check + pop (race condition fix)
    result = _search_results.pop(search_id, None)
    if result is None:
        await callback.answer("⏰ Результат устарел, повторите поиск")
        return

    data, _ = result  # Извлекаем data из tuple (data, timestamp)

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
