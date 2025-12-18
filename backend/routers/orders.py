from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from uuid import UUID
from io import BytesIO
from datetime import datetime
import math
from backend.models.database import get_supabase_client
from backend.models.schemas import Order, OrderCreate
from backend.services.excel import ExcelService
from backend.services.matching import MatchingService


def round_to_pack(qty: float, pack_qty: int) -> int:
    """Округление количества до целых упаковок"""
    if pack_qty <= 1:
        return int(math.ceil(qty))
    return math.ceil(qty / pack_qty) * pack_qty

router = APIRouter(prefix="/orders", tags=["orders"])

@router.get("/", response_model=list[Order])
async def list_orders(client_id: UUID = None, status: str = None):
    """Список заказов"""
    db = get_supabase_client()
    query = db.table('orders').select('*, clients(*), order_items(*, products(*))')

    if client_id:
        query = query.eq('client_id', str(client_id))
    if status:
        query = query.eq('status', status)

    response = query.order('created_at', desc=True).execute()
    return response.data or []

@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: UUID):
    """Получить заказ по ID"""
    db = get_supabase_client()
    response = db.table('orders')\
        .select('*, clients(*), order_items(*, products(*))')\
        .eq('id', str(order_id))\
        .single()\
        .execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return response.data

@router.post("/upload")
async def upload_order(
    file: UploadFile = File(...),
    client_id: UUID = Form(...),
    order_number: str = Form(None)
):
    """Загрузить заказ из Excel и выполнить маппинг"""
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Поддерживаются только Excel и CSV файлы")

    db = get_supabase_client()

    # Проверяем клиента
    client = db.table('clients').select('id').eq('id', str(client_id)).single().execute()
    if not client.data:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    # Парсим файл
    content = await file.read()
    items = ExcelService.parse_order_file(BytesIO(content), file.filename)

    if not items:
        raise HTTPException(status_code=400, detail="Файл пустой или не содержит позиций")

    # Создаём заказ
    order_data = {
        'client_id': str(client_id),
        'order_number': order_number,
        'source': 'excel',
        'status': 'processing',
        'original_file_url': file.filename
    }
    order_response = db.table('orders').insert(order_data).execute()
    order = order_response.data[0]
    order_id = order['id']

    # Маппинг позиций
    matcher = MatchingService()
    items_data = [item.model_dump() for item in items]
    matched_items = matcher.match_order_items(client_id, items_data)

    # Получаем pack_qty для всех товаров
    product_ids = [item['match'].get('product_id') for item in matched_items if item['match'].get('product_id')]
    pack_qty_map = {}
    if product_ids:
        products_resp = db.table('products').select('id, pack_qty').in_('id', product_ids).execute()
        for p in (products_resp.data or []):
            pack_qty_map[p['id']] = p.get('pack_qty', 1) or 1

    # Сохраняем позиции с округлением
    order_items = []
    needs_review_count = 0
    for item in matched_items:
        match = item['match']
        original_qty = item['quantity']
        product_id = match.get('product_id')
        pack_qty = pack_qty_map.get(product_id, 1) if product_id else 1
        rounded_qty = round_to_pack(original_qty, pack_qty)

        order_item = {
            'order_id': order_id,
            'client_sku': item['client_sku'],
            'client_name': item.get('client_name'),
            'quantity': rounded_qty,
            'original_quantity': original_qty if rounded_qty != original_qty else None,
            'mapped_product_id': product_id,
            'mapping_confidence': match.get('confidence'),
            'mapping_type': match.get('match_type'),
            'needs_review': match.get('needs_review', True),
            'reviewed': False
        }
        order_items.append(order_item)
        if match.get('needs_review'):
            needs_review_count += 1

    if order_items:
        db.table('order_items').insert(order_items).execute()

    # Обновляем статус заказа
    status = 'needs_review' if needs_review_count > 0 else 'processed'
    db.table('orders')\
        .update({'status': status, 'processed_at': datetime.utcnow().isoformat()})\
        .eq('id', order_id)\
        .execute()

    return {
        'order_id': order_id,
        'total_items': len(order_items),
        'needs_review': needs_review_count,
        'auto_mapped': len(order_items) - needs_review_count,
        'status': status
    }

@router.post("/{order_id}/export")
async def export_order(order_id: UUID):
    """Экспорт заказа в Excel для 1С"""
    db = get_supabase_client()

    # Получаем заказ с позициями
    response = db.table('orders')\
        .select('*, order_items(*, products(*))')\
        .eq('id', str(order_id))\
        .single()\
        .execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    order = response.data
    items = order.get('items', order.get('order_items', []))

    # Преобразуем для экспорта
    export_items = []
    for item in items:
        product = item.get('product') or item.get('products')
        export_items.append({
            'client_sku': item['client_sku'],
            'client_name': item.get('client_name', ''),
            'quantity': item['quantity'],
            'original_quantity': item.get('original_quantity'),
            'match': {
                'product_sku': product['sku'] if product else '',
                'product_name': product['name'] if product else '',
                'pack_qty': product.get('pack_qty', 1) if product else 1,
                'confidence': item.get('mapping_confidence', 0),
                'match_type': item.get('mapping_type', ''),
                'needs_review': item.get('needs_review', True)
            }
        })

    excel_bytes = ExcelService.export_order(export_items)

    # Обновляем статус
    db.table('orders')\
        .update({'exported_at': datetime.utcnow().isoformat()})\
        .eq('id', str(order_id))\
        .execute()

    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename=order_{order_id}.xlsx'}
    )

@router.put("/{order_id}/items/{item_id}/mapping")
async def update_item_mapping(order_id: UUID, item_id: UUID, product_id: UUID):
    """Ручное обновление маппинга позиции"""
    db = get_supabase_client()

    # Проверяем товар
    product = db.table('products').select('*').eq('id', str(product_id)).single().execute()
    if not product.data:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Обновляем позицию
    db.table('order_items')\
        .update({
            'mapped_product_id': str(product_id),
            'mapping_confidence': 100.0,
            'mapping_type': 'manual',
            'needs_review': False,
            'reviewed': True
        })\
        .eq('id', str(item_id))\
        .eq('order_id', str(order_id))\
        .execute()

    # Сохраняем маппинг для будущих заказов
    item = db.table('order_items')\
        .select('client_sku, orders(client_id)')\
        .eq('id', str(item_id))\
        .single()\
        .execute()

    if item.data:
        order_info = item.data.get('orders', {})
        client_id = order_info.get('client_id')
        if client_id:
            matcher = MatchingService()
            matcher.save_mapping(
                client_id=UUID(client_id),
                client_sku=item.data['client_sku'],
                product_id=product_id,
                confidence=100.0,
                match_type='manual',
                verified=True
            )

    return {"status": "updated"}

@router.post("/{order_id}/confirm")
async def confirm_order(order_id: UUID):
    """Подтвердить все маппинги заказа"""
    db = get_supabase_client()

    # Получаем заказ
    order = db.table('orders')\
        .select('client_id, order_items(*)')\
        .eq('id', str(order_id))\
        .single()\
        .execute()

    if not order.data:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    client_id = order.data['client_id']
    items = order.data.get('order_items', [])

    # Сохраняем все маппинги как верифицированные
    matcher = MatchingService()
    for item in items:
        if item.get('mapped_product_id'):
            matcher.save_mapping(
                client_id=UUID(client_id),
                client_sku=item['client_sku'],
                product_id=UUID(item['mapped_product_id']),
                confidence=item.get('mapping_confidence', 100),
                match_type=item.get('mapping_type', 'confirmed'),
                verified=True
            )

    # Обновляем статус заказа
    db.table('orders')\
        .update({'status': 'confirmed'})\
        .eq('id', str(order_id))\
        .execute()

    # Отмечаем все позиции как проверенные
    db.table('order_items')\
        .update({'reviewed': True, 'needs_review': False})\
        .eq('order_id', str(order_id))\
        .execute()

    return {"status": "confirmed", "mappings_saved": len(items)}
