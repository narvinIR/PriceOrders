import re
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from backend.models.schemas import OrderItemBase


def extract_pack_qty(name: str) -> int:
    """Извлечь количество в упаковке из названия товара"""
    if not name:
        return 1
    patterns = [
        r'\(уп\.?\s*(\d+)\s*шт\.?\)',  # (уп 20 шт), (уп.20шт)
        r'\((\d+)\s*шт\)',              # (20 шт)
        r'(\d+)\s*шт/кор',              # 100 шт/кор
        r'уп\.?\s*(\d+)\s*шт',          # уп 20 шт
        r'\((\d+)\s*шт/кор\)',          # (25 шт/кор)
    ]
    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 1


def extract_thread_type(name: str) -> str | None:
    """Извлечь тип резьбы из названия товара"""
    if not name:
        return None
    name_lower = name.lower()
    if 'вн.рез' in name_lower or 'вн рез' in name_lower or 'внутр' in name_lower:
        return 'внутренняя'
    if 'нар.рез' in name_lower or 'нар рез' in name_lower or 'наруж' in name_lower:
        return 'наружная'
    return None

class ExcelService:
    """Парсинг Excel файлов с заказами"""

    # Возможные названия колонок
    SKU_COLUMNS = ['артикул', 'sku', 'код', 'article', 'code', 'номер', 'арт', 'арт.']
    NAME_COLUMNS = ['название', 'наименование', 'name', 'товар', 'product', 'описание']
    QTY_COLUMNS = ['количество', 'qty', 'quantity', 'кол-во', 'кол', 'шт', 'count']

    @classmethod
    def parse_order_file(cls, file: BinaryIO, filename: str) -> list[OrderItemBase]:
        """Парсинг Excel/CSV файла с заказом"""
        # Определяем формат
        if filename.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8')
        else:
            df = pd.read_excel(file)

        # Нормализуем названия колонок
        df.columns = [str(col).lower().strip() for col in df.columns]

        # Находим нужные колонки
        sku_col = cls._find_column(df.columns, cls.SKU_COLUMNS)
        name_col = cls._find_column(df.columns, cls.NAME_COLUMNS)
        qty_col = cls._find_column(df.columns, cls.QTY_COLUMNS)

        if not sku_col and not name_col:
            raise ValueError("Не найдены колонки с артикулом или названием товара")

        items = []
        for _, row in df.iterrows():
            sku = str(row[sku_col]).strip() if sku_col and pd.notna(row[sku_col]) else ""
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
            qty = float(row[qty_col]) if qty_col and pd.notna(row[qty_col]) else 1.0

            # Пропускаем пустые строки
            if not sku and not name:
                continue

            items.append(OrderItemBase(
                client_sku=sku or name[:50],  # Если нет артикула, используем часть названия
                client_name=name,
                quantity=qty
            ))

        return items

    @classmethod
    def _find_column(cls, columns: list, candidates: list) -> str | None:
        """Поиск колонки по возможным названиям"""
        for col in columns:
            col_lower = col.lower()
            for candidate in candidates:
                if candidate in col_lower:
                    return col
        return None

    @classmethod
    def parse_catalog(cls, file: BinaryIO, filename: str) -> list[dict]:
        """Парсинг каталога товаров поставщика"""
        if filename.endswith('.csv'):
            df = pd.read_csv(file, encoding='utf-8')
        else:
            df = pd.read_excel(file)

        df.columns = [str(col).lower().strip() for col in df.columns]

        sku_col = cls._find_column(df.columns, cls.SKU_COLUMNS)
        name_col = cls._find_column(df.columns, cls.NAME_COLUMNS)

        if not sku_col:
            raise ValueError("Не найдена колонка с артикулом")
        if not name_col:
            raise ValueError("Не найдена колонка с названием")

        # Ищем дополнительные колонки
        category_candidates = ['категория', 'category', 'группа', 'раздел']
        brand_candidates = ['бренд', 'brand', 'производитель', 'марка']
        unit_candidates = ['единица', 'unit', 'ед.изм', 'ед', 'изм']
        price_candidates = ['цена', 'price', 'стоимость', 'розница']

        category_col = cls._find_column(df.columns, category_candidates)
        brand_col = cls._find_column(df.columns, brand_candidates)
        unit_col = cls._find_column(df.columns, unit_candidates)
        price_col = cls._find_column(df.columns, price_candidates)

        products = []
        for _, row in df.iterrows():
            sku = str(row[sku_col]).strip() if pd.notna(row[sku_col]) else ""
            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""

            if not sku or not name:
                continue

            product = {
                'sku': sku,
                'name': name,
                'category': str(row[category_col]).strip() if category_col and pd.notna(row[category_col]) else None,
                'brand': str(row[brand_col]).strip() if brand_col and pd.notna(row[brand_col]) else None,
                'unit': str(row[unit_col]).strip() if unit_col and pd.notna(row[unit_col]) else 'шт',
                'price': float(row[price_col]) if price_col and pd.notna(row[price_col]) else None,
                'pack_qty': extract_pack_qty(name),
                'attributes': {}
            }
            products.append(product)

        return products

    @classmethod
    def parse_jakko_catalog(cls, file: BinaryIO) -> list[dict]:
        """Парсинг прайса Jakko с несколькими листами"""
        xl = pd.ExcelFile(file)
        products = []

        # Категории из листа Содержание
        categories = {
            '1': 'Трубы ПЭ для воды',
            '2': 'Трубы PERT',
            '3': 'Трубы ППР',
            '4': 'Фитинги ППР',
            '5': 'Фитинги ППР с резьбой',
            '6': 'Запорная арматура ППР',
            '7': 'Трубы ПП малошумные',
            '8': 'Трубы канализационные ПП',
            '9': 'Трубы наружной канализации',
            '10': 'Трубы рифлёные',
            '11': 'Герметики и инструмент',
            '12': 'Прочее'
        }

        for sheet_name in xl.sheet_names:
            if sheet_name in ['Содержание', 'заказ']:
                continue

            try:
                df = pd.read_excel(file, sheet_name=sheet_name, header=None)

                # Заголовки в строке 4 (0-indexed)
                if len(df) < 5:
                    continue

                # Ищем колонки по заголовкам
                header_row = df.iloc[4]
                sku_col = None
                name_col = None
                price_col = None
                pack_col = None  # ПАКЕТ или УПАКОВКА
                box_col = None   # КОРОБКА
                thickness_col = None  # ТОЛЩИНА

                for idx, val in enumerate(header_row):
                    val_str = str(val).upper().strip()
                    if 'АРТИКУЛ' in val_str:
                        sku_col = idx
                    elif 'НОМЕНКЛАТУРА' in val_str:
                        name_col = idx
                    elif 'ЦЕНА' in val_str and price_col is None:
                        price_col = idx
                    elif val_str in ('ПАКЕТ', 'УПАКОВКА'):
                        pack_col = idx
                    elif val_str == 'КОРОБКА':
                        box_col = idx
                    elif val_str == 'ТОЛЩИНА':
                        thickness_col = idx

                if sku_col is None or name_col is None:
                    continue

                # Читаем данные начиная со строки 5
                for i in range(5, len(df)):
                    row = df.iloc[i]
                    sku = str(row.iloc[sku_col]).strip() if pd.notna(row.iloc[sku_col]) else ""
                    name = str(row.iloc[name_col]).strip() if pd.notna(row.iloc[name_col]) else ""

                    # Пропускаем строки без артикула или с заголовками
                    if not sku or sku == 'nan' or sku == 'АРТИКУЛ':
                        continue

                    # Очистка неразрывных пробелов
                    name = name.replace('\xa0', ' ').strip()
                    if not name or name == 'nan':
                        continue

                    # Цена (в прайсе указана базовая 0%)
                    price = None
                    base_price = None
                    if price_col is not None and pd.notna(row.iloc[price_col]):
                        try:
                            price = float(row.iloc[price_col])
                            base_price = round(price, 2)
                        except (ValueError, TypeError):
                            pass

                    # pack_qty из колонки ПАКЕТ/УПАКОВКА
                    pack_qty = 1
                    box_qty = None
                    if pack_col is not None and pd.notna(row.iloc[pack_col]):
                        val = str(row.iloc[pack_col]).strip()
                        # Формат может быть "25" или "55/660" (пакет/коробка)
                        if '/' in val:
                            parts = val.split('/')
                            try:
                                pack_qty = int(parts[0])
                                box_qty = int(parts[1]) if len(parts) > 1 else None
                            except (ValueError, TypeError):
                                pack_qty = extract_pack_qty(name)
                        else:
                            try:
                                pack_qty = int(float(val))
                            except (ValueError, TypeError):
                                pack_qty = extract_pack_qty(name)
                    else:
                        pack_qty = extract_pack_qty(name)

                    # Атрибуты (толщина, коробка, резьба)
                    attributes = {}
                    if thickness_col is not None and pd.notna(row.iloc[thickness_col]):
                        try:
                            attributes['thickness'] = float(row.iloc[thickness_col])
                        except (ValueError, TypeError):
                            pass
                    # box_qty из колонки или из формата "пакет/коробка"
                    if box_col is not None and pd.notna(row.iloc[box_col]):
                        try:
                            attributes['box_qty'] = int(row.iloc[box_col])
                        except (ValueError, TypeError):
                            pass
                    elif box_qty:
                        attributes['box_qty'] = box_qty
                    # Тип резьбы из названия
                    thread = extract_thread_type(name)
                    if thread:
                        attributes['thread_type'] = thread

                    products.append({
                        'sku': sku,
                        'name': name,
                        'category': categories.get(sheet_name, f'Категория {sheet_name}'),
                        'brand': 'Jakko',
                        'unit': 'шт',
                        'price': price,
                        'base_price': base_price,
                        'pack_qty': pack_qty,
                        'attributes': attributes
                    })

            except Exception as e:
                print(f"Ошибка при парсинге листа {sheet_name}: {e}")
                continue

        # Дедупликация по SKU (оставляем первый)
        seen_skus = set()
        unique_products = []
        for p in products:
            if p['sku'] not in seen_skus:
                seen_skus.add(p['sku'])
                unique_products.append(p)

        return unique_products

    @classmethod
    def is_jakko_format(cls, file: BinaryIO) -> bool:
        """Проверка является ли файл прайсом Jakko"""
        try:
            xl = pd.ExcelFile(file)
            sheets = xl.sheet_names
            file.seek(0)  # Сброс позиции для повторного чтения
            return 'Содержание' in sheets and len(sheets) > 5
        except Exception:
            return False

    @classmethod
    def export_order(cls, order_data: list[dict], include_mapping: bool = True) -> bytes:
        """Экспорт обработанного заказа в Excel для 1С"""
        rows = []
        for item in order_data:
            qty = item.get('quantity', 1)
            orig_qty = item.get('original_quantity')
            row = {
                'Артикул клиента': item.get('client_sku', ''),
                'Название клиента': item.get('client_name', ''),
                'Количество': qty,
            }
            if orig_qty and orig_qty != qty:
                row['Исходное кол-во'] = orig_qty

            if include_mapping:
                match = item.get('match', {})
                row['Артикул поставщика'] = match.get('product_sku', '')
                row['Название поставщика'] = match.get('product_name', '')
                row['Упаковка'] = match.get('pack_qty', 1)
                row['Совпадение %'] = match.get('confidence', 0)
                row['Тип маппинга'] = match.get('match_type', '')
                row['Требует проверки'] = 'Да' if match.get('needs_review', True) else 'Нет'

            rows.append(row)

        df = pd.DataFrame(rows)

        # Экспорт в BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Заказ')
        output.seek(0)
        return output.getvalue()
