import pandas as pd
from io import BytesIO
from uuid import UUID
from typing import BinaryIO
from backend.models.schemas import OrderItemBase

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
                'attributes': {}
            }
            products.append(product)

        return products

    @classmethod
    def export_order(cls, order_data: list[dict], include_mapping: bool = True) -> bytes:
        """Экспорт обработанного заказа в Excel для 1С"""
        rows = []
        for item in order_data:
            row = {
                'Артикул клиента': item.get('client_sku', ''),
                'Название клиента': item.get('client_name', ''),
                'Количество': item.get('quantity', 1),
            }

            if include_mapping:
                match = item.get('match', {})
                row['Артикул поставщика'] = match.get('product_sku', '')
                row['Название поставщика'] = match.get('product_name', '')
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
