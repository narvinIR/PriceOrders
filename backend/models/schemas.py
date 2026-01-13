from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import datetime
from uuid import UUID

# Products
class ProductBase(BaseModel):
    sku: str
    name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    unit: str = "шт"
    price: Optional[float] = None
    base_price: Optional[float] = None
    pack_qty: int = 1  # Количество в упаковке
    attributes: dict = Field(default_factory=dict)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    base_price: Optional[float] = None
    attributes: Optional[dict] = None

class Product(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Clients
class ClientBase(BaseModel):
    name: str
    code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    settings: dict = Field(default_factory=dict)

class ClientCreate(ClientBase):
    pass

class Client(ClientBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Mappings
class MappingBase(BaseModel):
    client_id: UUID
    client_sku: str
    product_id: UUID
    confidence: float
    match_type: str
    verified: bool = False

class MappingCreate(MappingBase):
    pass

class Mapping(MappingBase):
    id: UUID
    verified_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Orders
class OrderItemBase(BaseModel):
    client_sku: str
    client_name: Optional[str] = None
    quantity: float = 1.0

class OrderItem(OrderItemBase):
    id: UUID
    order_id: UUID
    mapped_product_id: Optional[UUID] = None
    mapping_confidence: Optional[float] = None
    mapping_type: Optional[str] = None
    needs_review: bool = False
    reviewed: bool = False
    original_quantity: Optional[float] = None  # Исходное кол-во до округления
    # Populated from join
    product: Optional[Product] = None

    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    client_id: UUID
    order_number: Optional[str] = None
    source: str = "excel"

class OrderCreate(OrderBase):
    items: list[OrderItemBase] = []

class Order(OrderBase):
    id: UUID
    status: str
    original_file_url: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    exported_at: Optional[datetime] = None
    items: list[OrderItem] = []
    client: Optional[Client] = None

    model_config = ConfigDict(from_attributes=True)

# Matching Result
class MatchResult(BaseModel):
    product_id: Optional[UUID] = None
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    confidence: float
    match_type: str
    needs_review: bool
    pack_qty: int = 1  # Количество в упаковке
