"""
Inline клавиатуры для бота.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_match_keyboard(search_id: str, needs_review: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения/отклонения соответствия.

    Args:
        search_id: ID результата поиска
        needs_review: Требуется ли проверка (если False - автоподтверждение)
    """
    if not needs_review:
        # Высокий confidence - только кнопка отклонения
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтверждено автоматически",
                    callback_data=f"auto:{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{search_id}"
                )
            ]
        ])

    # Требуется проверка - обе кнопки
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"confirm:{search_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"reject:{search_id}"
            )
        ]
    ])


def get_upload_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после обработки Excel"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📥 Скачать результат",
                callback_data="download_result"
            )
        ]
    ])
