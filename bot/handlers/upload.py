"""
Обработчик загрузки файлов и текстовых списков артикулов.
Поддержка: Excel (.xlsx, .xls), CSV (.csv), текстовые списки.
Возвращает результат в Excel файле.
"""

import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime


from aiogram import Bot, F, Router
from aiogram.types import FSInputFile, Message

logger = logging.getLogger(__name__)

# Ограничение размера файла (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

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


def _match_single_item(matcher, item: dict, session_id=None) -> dict:
    """Обработка одного товара (для параллельного запуска)."""
    client_sku = item.get("sku", "")
    client_name = item.get("name", "")
    qty = item.get("qty", 1)

    result = matcher.match_item(
        client_id=session_id,  # Используем session_id для кэширования маппингов
        client_sku=client_sku,
        client_name=client_name or client_sku,
    )

    if result.product_sku:
        pack_qty = result.pack_qty or 1
        if pack_qty > 1 and qty > 0:
            packs_needed = (qty + pack_qty - 1) // pack_qty
            total_qty = packs_needed * pack_qty
        else:
            total_qty = qty

        return {
            "Запрос": client_sku or client_name,
            "Артикул Jakko": result.product_sku,
            "Название Jakko": result.product_name,
            "Исх. кол-во": qty,  # Исходное количество клиента
            "Кол-во": total_qty,
            "Упаковка": pack_qty,
            "Точность": f"{result.confidence:.0f}%",
            "Метод": result.match_type,
            "_matched": True,
        }
    else:
        return {
            "Запрос": client_sku or client_name,
            "Артикул Jakko": "❌ НЕ НАЙДЕНО",
            "Название Jakko": "",
            "Исх. кол-во": qty,
            "Кол-во": qty,
            "Упаковка": 1,
            "Точность": "0%",
            "Метод": "not_found",
            "_matched": False,
        }


async def _process_items_parallel(items: list) -> tuple[list, int, int]:
    """
    Параллельная обработка товаров (3-5x быстрее).
    Каждый товар обрабатывается в отдельном потоке.
    """
    matcher = get_matcher()

    # Используем client_id клиента Эльф для загрузки импортированных маппингов
    # TODO: в будущем определять client_id по Telegram user_id
    from uuid import UUID

    elf_client_id = UUID("5013baff-4e85-448c-a8af-a90594407e43")

    # Запускаем все товары параллельно
    tasks = [
        asyncio.to_thread(_match_single_item, matcher, item, elf_client_id)
        for item in items
    ]

    # Таймаут 180 сек (LLM matching ~3 сек на позицию)
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=180.0
        )
    except TimeoutError:
        logger.error("⏰ Timeout при обработке заказа (180 сек)")
        # Возвращаем частичные результаты
        results = [
            {
                "Запрос": item.get("sku", "") or item.get("name", ""),
                "Артикул Jakko": "⏰ TIMEOUT",
                "Название Jakko": "Превышено время обработки",
                "Кол-во": item.get("qty", 1),
                "Упаковка": 1,
                "Точность": "0%",
                "Метод": "timeout",
                "_matched": False,
            }
            for item in items
        ]

    # Фильтруем исключения
    valid_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(f"❌ Ошибка обработки позиции {i}: {r}")
            valid_results.append(
                {
                    "Запрос": items[i].get("sku", "") or items[i].get("name", ""),
                    "Артикул Jakko": "❌ ОШИБКА",
                    "Название Jakko": str(r)[:50],
                    "Кол-во": items[i].get("qty", 1),
                    "Упаковка": 1,
                    "Точность": "0%",
                    "Метод": "error",
                    "_matched": False,
                }
            )
        else:
            valid_results.append(r)
    results = valid_results

    # Подсчитываем статистику
    matched = sum(1 for r in results if r.get("_matched"))
    not_found = len(results) - matched

    # Убираем служебное поле
    for r in results:
        r.pop("_matched", None)

    return list(results), matched, not_found


# Remove pandas import at top level first (done via separate edit or manually?
# I will supply the full replacement of process_items and top imports in two chunks if needed.
# Since I can't do multiple chunks easily without MultiReplace, I'll do process_items here and assume import removal later or now.)


async def process_items(message: Message, items: list):
    """
    Обработка списка артикулов и вывод результата в Excel.
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

    # Создаём Excel файл (через API ExcelService без pandas)
    from backend.services.excel import ExcelService

    # Prepare data for export
    export_data = []
    for r in results:
        # Adapt result dict to structure expected by ExcelService or use dict directly if compatible
        # result dict structure from _match_single_item:
        # {"Запрос": ..., "Артикул Jakko": ..., ... "Точность": ...}
        # ExcelService.export_order expects:
        # {'client_sku', 'client_name', 'quantity', 'match': {'product_sku', ...}}

        # We need to adapt existing `results` format to what `ExcelService.export_order` expects,
        # OR update `ExcelService.export_order` to handle flat dicts?
        # Better: let's rewrite `process_items` logic to construct the list for `ExcelService`.

        # Accessing keys from `_match_single_item`:
        item_data = {
            "client_sku": r.get("Запрос", ""),
            "client_name": "",  # "Запрос" usually holds sku or name
            "quantity": r.get("Исх. кол-во", 1),
            "match": {
                "product_sku": r.get("Артикул Jakko", ""),
                "product_name": r.get("Название Jakko", ""),
                "pack_qty": r.get("Упаковка", 1),
                "confidence": r.get("Точность", "0%").replace("%", ""),
                "match_type": r.get("Метод", ""),
                "needs_review": "NO_MATCH" in str(r.get("Артикул Jakko", ""))
                or int(r.get("Точность", "0%").replace("%", "")) < 80,
            },
        }
        export_data.append(item_data)

    excel_bytes = ExcelService.export_order(export_data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"jakko_order_{timestamp}.xlsx"

    # Send document
    from aiogram.types import BufferedInputFile

    doc = BufferedInputFile(excel_bytes, filename=filename)

    await message.answer_document(
        doc,
        caption=f"✅ <b>Готово!</b>\n📦 Найдено: {matched}\n❌ Не найдено: {not_found}",
    )
    logger.info("✅ Файл отправлен!")


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    """Обработка фото рукописного заказа через OCR"""
    await message.answer("📷 Получил фото, распознаю текст...")

    try:
        # Берём наибольший размер фото
        photo = message.photo[-1]

        # Скачиваем
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Конвертируем в bytes
        image_bytes = file_bytes.read() if hasattr(file_bytes, "read") else file_bytes

        # OCR
        from backend.services.ocr_service import get_ocr_service

        ocr = get_ocr_service()
        if not ocr:
            await message.answer("OCR не настроен (нет OPENROUTER_API_KEY)")
            return

        items = ocr.recognize_order(image_bytes)

        if not items:
            await message.answer(
                "Не удалось распознать текст на фото.\n\n"
                "Попробуйте:\n"
                "• Сделать фото более чётким\n"
                "• Отправить список текстом"
            )
            return

        logger.info(f"OCR: распознано {len(items)} позиций")
        await process_items(message, items)

    except Exception as e:
        logger.error(f"Ошибка OCR: {e}", exc_info=True)
        await message.answer(f"Ошибка распознавания: {e}")


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    """Обработка загруженного файла (Excel/CSV)"""
    document = message.document
    filename = document.file_name.lower()

    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer(
            f"⚠️ Файл слишком большой ({document.file_size // 1024 // 1024} MB).\n"
            f"Максимальный размер: {MAX_FILE_SIZE // 1024 // 1024} MB"
        )
        return

    # Excel/CSV processing
    if not filename.endswith((".xlsx", ".xls", ".csv")):
        # Check if image for OCR (moved here for cleaner logic flow)
        if filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            await message.answer("📷 Получил фото, распознаю текст...")
            # ... existing OCR logic (omitted for brevity if unchanged, but need to keep it?)
            # The user asked to remove pandas.
            # I should keep OCR logic but cleaner.
            # For now, let's just focus on Excel/CSV part.
            return await handle_photo_doc(message, bot)  # delegating

        await message.answer(
            "⚠️ Поддерживаются: Excel, CSV, фото\n\n" "Или отправьте текст с артикулами."
        )
        return

    await message.answer("📥 Получил файл, обрабатываю...")

    tmp_path = None
    try:
        suffix = ".csv" if filename.endswith(".csv") else ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            await bot.download(document, tmp.name)
            tmp_path = tmp.name

        # Используем ExcelService (без pandas)
        from backend.services.excel import ExcelService

        with open(tmp_path, "rb") as f:
            # ExcelService возвращает список OrderItemBase
            order_items = ExcelService.parse_order_file(f, filename)

        items = []
        for item in order_items:
            # Convert OrderItemBase to dict for internal processing
            items.append(
                {
                    "sku": item.client_sku,
                    "name": item.client_name,
                    "qty": int(item.quantity),
                }
            )

        logger.info(f"✅ Parsed {len(items)} items from {filename}")

        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

        await process_items(message, items)

    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        logger.error(f"❌ Ошибка обработки файла: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка обработки файла: {e}")


# Separate OCR handler for documents to keep main handler clean
async def handle_photo_doc(message: Message, bot: Bot):
    try:
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read() if hasattr(file_bytes, "read") else file_bytes

        from backend.services.ocr_service import get_ocr_service

        ocr = get_ocr_service()
        if not ocr:
            await message.answer("❌ OCR не настроен")
            return

        items = ocr.recognize_order(image_bytes)
        if not items:
            await message.answer("❌ Не удалось распознать текст на фото")
            return

        await process_items(message, items)
    except Exception as e:
        logger.error(f"OCR Doc Error: {e}")
        await message.answer(f"Ошибка: {e}")


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
    if text.startswith("/"):
        return

    # Игнорируем короткие сообщения (меньше 3 символов)
    if len(text) < 3:
        return

    lines = text.split("\n")
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Парсим: название [количество]
        # Форматы клиентов:
        #   "Труба ПП (1,5 мм) 50х0.15  шт  730" → sku="Труба ПП (1,5 мм) 50х0.15", qty=730
        #   "Труба ПП (2,2 мм) 110х1.0  шт  1 300" → sku="Труба ПП...", qty=1300
        #   "Тройник ПП 40-  400шт" → sku="Тройник ПП 40", qty=400
        #   "СТкв отвод 110 /40/ !" → sku="СТкв отвод 110", qty=40

        # Убираем TAB → пробел, убираем ! (маркер клиента)
        line = line.replace("\t", " ").replace("!", "").strip()

        # Паттерн 0: формат "название N шт" в конце (любое количество)
        # Примеры: "Муфта компрессионная 20 Tebo/UNIO 60 шт", "9 (30) Труба ПП 100 шт"
        match_qty_sht = re.search(r"\s+(\d+)\s*шт\.?\s*$", line, re.IGNORECASE)
        if match_qty_sht:
            qty = int(match_qty_sht.group(1))
            sku = line[: match_qty_sht.start()].strip()
            # Убираем номер строки и количество в скобках из начала
            # "9 (30) Муфта..." → "Муфта..."
            sku = re.sub(r"^\d+\s*(\(\d+\))?\s*", "", sku).strip()
        else:
            # Паттерн 1: формат "название  шт  число" (Эльф формат)
            match_elf = re.match(r"^(.+?)\s+шт\s+([\d\s]+)$", line, re.IGNORECASE)
            if match_elf:
                sku = match_elf.group(1).strip()
                qty_str = match_elf.group(2).replace(" ", "")  # "1 300" → "1300"
                try:
                    qty = int(qty_str)
                except ValueError:
                    qty = 1
            else:
                # Паттерн 2: формат СТ "/число/" - количество в слешах
                match_st = re.search(r"/(\d{1,4})/\s*$", line)
                if match_st:
                    qty = int(match_st.group(1))
                    sku = re.sub(r"\s*/\d+/\s*$", "", line).strip()
                else:
                    # Паттерн 3: название[-] количество[шт|м.|м|штук]
                    match = re.match(
                        r"^(.+?)[-\s]+(\d{1,4})\s*(?:шт\.?|штук|м\.?|метр\.?)?\s*$",
                        line,
                        re.IGNORECASE,
                    )
                    if match:
                        sku = match.group(1).strip().rstrip("-")
                        qty = int(match.group(2))
                    else:
                        # Fallback: число 1-9999 в конце через пробел
                        match2 = re.match(r"^(.+?)\s+(\d{1,4})\s*$", line)
                        if match2:
                            sku = match2.group(1).strip()
                            qty = int(match2.group(2))
                        else:
                            sku = line
                            qty = 1

        if sku:
            items.append({"sku": sku, "name": "", "qty": qty})

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
