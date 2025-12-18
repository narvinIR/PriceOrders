from fastapi import APIRouter, HTTPException, UploadFile, File
from uuid import UUID
from backend.models.database import get_supabase_client
from backend.models.schemas import Product, ProductCreate, ProductUpdate
from backend.services.excel import ExcelService

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=list[Product])
async def list_products(skip: int = 0, limit: int = 100):
    """Список товаров каталога"""
    db = get_supabase_client()
    response = db.table('products')\
        .select('*')\
        .range(skip, skip + limit - 1)\
        .execute()
    return response.data or []

@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: UUID):
    """Получить товар по ID"""
    db = get_supabase_client()
    response = db.table('products')\
        .select('*')\
        .eq('id', str(product_id))\
        .single()\
        .execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return response.data

@router.post("/", response_model=Product)
async def create_product(product: ProductCreate):
    """Создать товар"""
    db = get_supabase_client()
    response = db.table('products')\
        .insert(product.model_dump())\
        .execute()
    return response.data[0]

@router.put("/{product_id}", response_model=Product)
async def update_product(product_id: UUID, product: ProductUpdate):
    """Обновить товар"""
    db = get_supabase_client()
    update_data = {k: v for k, v in product.model_dump().items() if v is not None}
    response = db.table('products')\
        .update(update_data)\
        .eq('id', str(product_id))\
        .execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return response.data[0]

@router.delete("/{product_id}")
async def delete_product(product_id: UUID):
    """Удалить товар"""
    db = get_supabase_client()
    db.table('products').delete().eq('id', str(product_id)).execute()
    return {"status": "deleted"}

@router.post("/upload")
async def upload_catalog(file: UploadFile = File(...)):
    """Загрузить каталог из Excel"""
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Поддерживаются только Excel и CSV файлы")

    content = await file.read()
    from io import BytesIO
    file_buffer = BytesIO(content)

    # Определяем формат файла
    if file.filename.endswith('.xlsx') and ExcelService.is_jakko_format(file_buffer):
        file_buffer.seek(0)
        products = ExcelService.parse_jakko_catalog(file_buffer)
        format_type = "jakko"
    else:
        file_buffer.seek(0)
        products = ExcelService.parse_catalog(file_buffer, file.filename)
        format_type = "standard"

    db = get_supabase_client()
    # Bulk upsert
    if products:
        db.table('products').upsert(products, on_conflict='sku').execute()

    return {"uploaded": len(products), "format": format_type}

@router.get("/search/{query}")
async def search_products(query: str, limit: int = 10):
    """Поиск товаров по названию или артикулу"""
    db = get_supabase_client()
    # Поиск по SKU
    response = db.table('products')\
        .select('*')\
        .or_(f"sku.ilike.%{query}%,name.ilike.%{query}%")\
        .limit(limit)\
        .execute()
    return response.data or []
