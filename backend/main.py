from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import products_router, clients_router, orders_router

app = FastAPI(
    title="PriceOrders API",
    description="API для маппинга артикулов клиентов B2B",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(products_router)
app.include_router(clients_router)
app.include_router(orders_router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "PriceOrders API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
