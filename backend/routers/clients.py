from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.models.database import get_supabase_client
from backend.models.schemas import Client, ClientCreate

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=list[Client])
async def list_clients():
    """Список клиентов"""
    db = get_supabase_client()
    response = db.table('clients').select('*').execute()
    return response.data or []

@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: UUID):
    """Получить клиента по ID"""
    db = get_supabase_client()
    response = db.table('clients')\
        .select('*')\
        .eq('id', str(client_id))\
        .single()\
        .execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return response.data

@router.post("/", response_model=Client)
async def create_client(client: ClientCreate):
    """Создать клиента"""
    db = get_supabase_client()
    response = db.table('clients')\
        .insert(client.model_dump())\
        .execute()
    return response.data[0]

@router.put("/{client_id}", response_model=Client)
async def update_client(client_id: UUID, client: ClientCreate):
    """Обновить клиента"""
    db = get_supabase_client()
    response = db.table('clients')\
        .update(client.model_dump())\
        .eq('id', str(client_id))\
        .execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return response.data[0]

@router.delete("/{client_id}")
async def delete_client(client_id: UUID):
    """Удалить клиента"""
    db = get_supabase_client()
    db.table('clients').delete().eq('id', str(client_id)).execute()
    return {"status": "deleted"}

@router.get("/{client_id}/mappings")
async def get_client_mappings(client_id: UUID, verified_only: bool = False):
    """Получить маппинги клиента"""
    db = get_supabase_client()
    query = db.table('mappings')\
        .select('*, products(*)')\
        .eq('client_id', str(client_id))

    if verified_only:
        query = query.eq('verified', True)

    response = query.execute()
    return response.data or []
