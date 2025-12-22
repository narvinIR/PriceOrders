"""
Обработчик загрузки файлов и текстовых списков артикулов.
Поддержка: Excel (.xlsx, .xls), CSV (.csv), текстовые списки.
Возвращает результат в Excel файле.
"""
import asyncio
import os
import re
import logging
import tempfile
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, FSInputFile
import pandas as pd

logger = logging.getLogger(__name__)

router = Router()

# Singleton для MatchingService - ML модель загружается ОДИН раз
_matcher = None


def get_matcher():
    """Ленивая инициализация MatchingService"""
    global _matcher
    if _matcher is None:
        logger.info("🔧 Инициализация MatchingService...")
        from backend.services.matching import MatchingService
        _matcher = MatchingService()
        logger.info("✅ MatchingService готов")
    return _matcher


def _match_single_item(matcher, item: dict) -> dict:
    """Обработка одного товара (для параллельного запуска)."""
    client_sku = item.get('sku', '')
    client_name = item.get('name', '')
    qty = item.get('qty', 1)

    result = matcher.match_item(
        client_id=None,
        client_sku=client_sku,
        client_name=client_name or client_sku
    )

    if result.product_sku:
        pack_qty = result.pack_qty or 1
        if pack_qty > 1 and qty > 0:
            packs_needed = (qty + pack_qty - 1) // pack_qty
            total_qty = packs_needed * pack_qty
        else:
            total_qty = qty

        return {
            'Запрос': client_sku or client_name,
            'Артикул Jakko': result.product_sku,
            'Название Jakko': result.product_name,
            'Кол-во': total_qty,
            'Упаковка': pack_qty,
            'Точность': f"{result.confidence:.0f}%",
            'Метод': result.match_type,
            '_matched': True,
        }
    else:
        return {
            'Запрос': client_sku or client_name,
            'Артикул Jakko': '❌ НЕ НАЙДЕНО',
            'Название Jakko': '',
            'Кол-во': qty,
            'Упаковка': 1,
            'Точность': '0%',
            'Метод': 'not_found',
            '_matched': False,
        }


async def _process_items_parallel(items: list) -> tuple[list, int, int]:
    """
    Параллельная обработка товаров (3-5x быстрее).
    Каждый товар обрабатывается в отдельном потоке.
    """
    matcher = get_matcher()

    # Запускаем все товары параллельно
    tasks = [
        asyncio.to_thread(_match_single_item, matcher, item)
        for item in items
    ]
    results = await asyncio.gather(*tasks)

    # Подсчитываем статистику
    matched = sum(1 for r in results if r.get('_matched'))
    not_found = len(results) - matched

    # Убираем служебное поле
    for r in results:
        r.pop('_matched', None)

    return list(results), matched, not_found


async def process_items(message: Message, items: list):
    """
    Обработка списка артикулов и вывод результата в Excel.

    Args:
        message: Telegram message
        items: список dict с ключами 'sku', 'name', 'qty'
    """
    if not items:
        await message.answer("❌ Не найдено позиций для обработки")
        return

    logger.info(f"⚙️ process_items: {len(items)} позиций")
    await message.answer(f"🔍 Обрабатываю {len(items)} позиций...")

    try:
        # Параллельная обработка (3-5x быстрее)
        results, matched, not_found = await _process_items_parallel(items)
    except Exception as e:
        logger.error(f"❌ Ошибка matching: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при обработке: {e}")
        return

    logger.info(f"✅ Matching: {matched} найдено, {not_found} не найдено")

    # Создаём Excel файл
    df = pd.DataFrame(results)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"jakko_order_{timestamp}.xlsx"

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp_path = tmp.name

    # Сохраняем с форматированием
    with pd.ExcelWriter(tmp_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заказ')
        worksheet = writer.sheets['Заказ']
        # Ширина колонок
        worksheet.column_dimensions['A'].width = 25
        worksheet.column_dimensions['B'].width = 15
        worksheet.column_dimensions['C'].width = 50
        worksheet.column_dimensions['D'].width = 10
        worksheet.column_dimensions['E'].width = 10
        worksheet.column_dimensions['F'].width = 10
        worksheet.column_dimensions['G'].width = 15

    # Отправляем файл
    logger.info("📤 Отправляю результат...")
    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"📦 Найдено: {matched} из {len(items)}\n"
        f"❌ Не найдено: {not_found}"
    )

    doc = FSInputFile(tmp_path, filename=filename)
    await message.answer_document(doc, caption="📎 Ваш заказ готов")
    logger.info("✅ Файл отправлен!")

    # Удаляем временный файл
    os.unlink(tmp_path)


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Обработка загруженного файла (Excel/CSV)"""
    document = message.document
    filename = document.file_name.lower()

    # Проверяем тип файла
    if not filename.endswith(('.xlsx', '.xls', '.csv')):
        await message.answer(
            "⚠️ Поддерживаются файлы: Excel (.xlsx, .xls), CSV (.csv)\n\n"
            "Или отправьте текстовый список артикулов (каждый с новой строки)."
        )
        return

    await message.answer("📥 Получил файл, обрабатываю...")

    try:
        # Определяем расширение для временного файла
        suffix = '.csv' if filename.endswith('.csv') else '.xlsx'

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            await bot.download(document, tmp.name)
            tmp_path = tmp.name

        # Парсим файл
        if filename.endswith('.csv'):
            # Пробуем разные разделители
            for sep in [';', ',', '\t']:
                try:
                    df = pd.read_csv(tmp_path, sep=sep)
                    if len(df.columns) > 1:
                        break
                except:
                    continue
            else:
                df = pd.read_csv(tmp_path)
        else:
            df = pd.read_excel(tmp_path)

        # Ищем колонки
        sku_col = None
        name_col = None
        qty_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if any(x in col_lower for x in ['артикул', 'sku', 'код', 'арт']):
                sku_col = col
            elif any(x in col_lower for x in ['название', 'наименование', 'name', 'товар']):
                name_col = col
            elif any(x in col_lower for x in ['количество', 'кол-во', 'qty', 'шт', 'кол']):
                qty_col = col

        # Если не нашли колонки, берём первую как артикул
        if not sku_col and not name_col:
            if len(df.columns) >= 1:
                sku_col = df.columns[0]
            if len(df.columns) >= 2:
                qty_col = df.columns[1]

        # Собираем items
        items = []
        for idx, row in df.iterrows():
            sku = str(row.get(sku_col, '')).strip() if sku_col else ''
            name = str(row.get(name_col, '')).strip() if name_col else ''

            # Парсим количество
            qty_raw = row.get(qty_col, 1) if qty_col else 1
            try:
                qty = int(float(qty_raw)) if pd.notna(qty_raw) else 1
            except:
                qty = 1

            if sku or name:
                items.append({'sku': sku, 'name': name, 'qty': qty})

        os.unlink(tmp_path)
        await process_items(message, items)

    except Exception as e:
        await message.answer(f"❌ Ошибка обработки файла: {e}")


@router.message(F.text)
async def handle_text_list(message: Message):
    """
    Обработка текстового списка артикулов.
    Формат: каждый артикул с новой строки, опционально количество через пробел/табуляцию.

    Примеры:
    202051110R
    202051110R 5
    Труба ПП 110-2000  10
    """
    # КРИТИЧНО: Защита от бесконечного цикла
    # Бот может получить свои же ответы как новые updates
    if message.from_user.is_bot:
        return

    text = message.text.strip()

    # Игнорируем команды
    if text.startswith('/'):
        return

    # Игнорируем короткие сообщения (меньше 3 символов)
    if len(text) < 3:
        return

    lines = text.split('\n')
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Парсим: название [количество]
        # Форматы клиентов:
        #   "Тройник ПП 40-  400шт" → sku="Тройник ПП 40", qty=400
        #   "Труба арм. 90(20)- 156 м." → sku="Труба арм. 90(20)", qty=156
        #   "Труба PN25  40*6,7	52" → sku="Труба PN25 40*6,7", qty=52
        #   "СТкв отвод 110 /40/ !" → sku="СТкв отвод 110", qty=40
        #   "Хомут 110 80" → sku="Хомут 110", qty=80

        # Убираем TAB → пробел, убираем ! (маркер клиента)
        line = line.replace('\t', ' ').replace('!', '').strip()

        # Паттерн 0: формат СТ "/число/" - количество в слешах
        # Пример: "СТкв отвод 110 угол 45гр /40/" → qty=40
        match_st = re.search(r'/(\d+)/\s*$', line)
        if match_st:
            qty = int(match_st.group(1))
            sku = re.sub(r'\s*/\d+/\s*$', '', line).strip()
        else:
            # Паттерн 1: название[-] количество[шт|м.|м|штук]
            match = re.match(
                r'^(.+?)[-\s]+(\d+)\s*(?:шт\.?|штук|м\.?|метр\.?)?\s*$',
                line,
                re.IGNORECASE
            )
            if match:
                sku = match.group(1).strip().rstrip('-')
                qty = int(match.group(2))
            else:
                # Fallback: число в конце через пробел
                match2 = re.match(r'^(.+?)\s+(\d+)\s*$', line)
                if match2:
                    sku = match2.group(1).strip()
                    qty = int(match2.group(2))
                else:
                    sku = line
                    qty = 1

        if sku:
            items.append({'sku': sku, 'name': '', 'qty': qty})

    if items:
        logger.info(f"📝 Получено {len(items)} позиций")
        try:
            await process_items(message, items)
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}", exc_info=True)
            await message.answer(f"❌ Ошибка обработки: {e}")
    else:
        await message.answer(
            "🔍 Отправьте артикул или название товара.\n\n"
            "<b>Примеры:</b>\n"
            "<code>Труба ПП 110×2000</code>\n"
            "<code>202051110R</code>"
        )
