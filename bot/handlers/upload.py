"""
Обработчик загрузки Excel файлов с заказами.
"""
import os
import tempfile
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
import pandas as pd

from bot.config import CONFIDENCE_THRESHOLD

router = Router()


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Обработка загруженного документа"""
    document = message.document

    # Проверяем тип файла
    if not document.file_name.endswith(('.xlsx', '.xls')):
        await message.answer(
            "⚠️ Поддерживаются только Excel файлы (.xlsx, .xls)\n\n"
            "Отправьте файл заказа в формате Excel."
        )
        return

    await message.answer("📥 Получил файл, обрабатываю...")

    try:
        # Скачиваем файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            await bot.download(document, tmp.name)
            tmp_path = tmp.name

        # Парсим Excel
        df = pd.read_excel(tmp_path)

        # Ищем колонки с артикулом и названием
        sku_col = None
        name_col = None
        qty_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if any(x in col_lower for x in ['артикул', 'sku', 'код', 'арт']):
                sku_col = col
            elif any(x in col_lower for x in ['название', 'наименование', 'name', 'товар']):
                name_col = col
            elif any(x in col_lower for x in ['количество', 'кол-во', 'qty', 'шт']):
                qty_col = col

        if not sku_col and not name_col:
            await message.answer(
                "❌ Не удалось найти колонки с артикулом или названием.\n\n"
                "Убедитесь, что в файле есть колонки:\n"
                "• Артикул / SKU / Код\n"
                "• Название / Наименование\n"
                "• Количество (опционально)"
            )
            os.unlink(tmp_path)
            return

        await message.answer(f"📊 Найдено {len(df)} позиций. Запускаю matching...")

        # Matching
        from backend.services.matching import MatchingService
        matcher = MatchingService()
        client_id = str(message.from_user.id)

        results = []
        matched = 0
        needs_review = 0
        not_found = 0

        for idx, row in df.iterrows():
            client_sku = str(row.get(sku_col, '')) if sku_col else ''
            client_name = str(row.get(name_col, '')) if name_col else ''
            qty = row.get(qty_col, 1) if qty_col else 1

            result = matcher.match_item(
                client_id=client_id,
                client_sku=client_sku,
                client_name=client_name
            )

            results.append({
                'Артикул клиента': client_sku,
                'Название клиента': client_name,
                'Количество': qty,
                'SKU Jakko': result.product_sku or '',
                'Название Jakko': result.product_name or '',
                'Confidence': result.confidence,
                'Метод': result.match_type,
                'Проверка': 'Да' if result.needs_review else 'Нет',
                'Упаковка': result.pack_qty or 1,
            })

            if result.match_type == 'not_found':
                not_found += 1
            elif result.needs_review:
                needs_review += 1
            else:
                matched += 1

        # Создаём результирующий файл
        result_df = pd.DataFrame(results)
        result_path = tmp_path.replace('.xlsx', '_result.xlsx')
        result_df.to_excel(result_path, index=False)

        # Отправляем результат
        text = f"""
✅ <b>Обработка завершена!</b>

<b>Статистика:</b>
• Всего позиций: {len(results)}
• Точные совпадения: {matched}
• Требуют проверки: {needs_review}
• Не найдено: {not_found}

<b>Точность:</b> {(matched / len(results) * 100):.1f}%
"""

        await message.answer(text)

        # Отправляем файл
        result_file = FSInputFile(result_path, filename=f"result_{document.file_name}")
        await message.answer_document(
            result_file,
            caption="📎 Результат обработки заказа"
        )

        # Удаляем временные файлы
        os.unlink(tmp_path)
        os.unlink(result_path)

    except Exception as e:
        await message.answer(f"❌ Ошибка обработки: {e}")
