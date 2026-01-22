import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import analytics_router, clients_router, orders_router, products_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PriceOrders API",
    description="API для маппинга артикулов клиентов B2B",
    version="1.0.0"
)

# CORS - ограничиваем до конкретных доменов
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Роутеры
app.include_router(products_router)
app.include_router(clients_router)
app.include_router(orders_router)
app.include_router(analytics_router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "PriceOrders API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/health/live")
async def health_live():
    """Liveness probe - приложение работает"""
    return {"status": "alive"}

@app.get("/health/ready")
async def health_ready():
    """Readiness probe - приложение готово обрабатывать запросы"""
    try:
        from backend.models.database import get_supabase_client
        db = get_supabase_client()
        db.table('products').select('id').limit(1).execute()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "not_ready", "database": "disconnected", "error": str(e)}
