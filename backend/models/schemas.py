from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Products
class ProductBase(BaseModel):
    sku: str
    name: str
    category: str | None = None
    brand: str | None = None
    unit: str = "шт"
    price: float | None = None
    base_price: float | None = None
    pack_qty: int = 1  # Количество в упаковке
    attributes: dict = Field(default_factory=dict)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    unit: str | None = None
    price: float | None = None
    base_price: float | None = None
    attributes: dict | None = None

class Product(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Clients
class ClientBase(BaseModel):
    name: str
    code: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
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
    verified_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Orders
class OrderItemBase(BaseModel):
    client_sku: str
    client_name: str | None = None
    quantity: float = 1.0

class OrderItem(OrderItemBase):
    id: UUID
    order_id: UUID
    mapped_product_id: UUID | None = None
    mapping_confidence: float | None = None
    mapping_type: str | None = None
    needs_review: bool = False
    reviewed: bool = False
    original_quantity: float | None = None  # Исходное кол-во до округления
    # Populated from join
    product: Product | None = None

    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    client_id: UUID
    order_number: str | None = None
    source: str = "excel"

class OrderCreate(OrderBase):
    items: list[OrderItemBase] = []

class Order(OrderBase):
    id: UUID
    status: str
    original_file_url: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    exported_at: datetime | None = None
    items: list[OrderItem] = []
    client: Client | None = None

    model_config = ConfigDict(from_attributes=True)

# Matching Result
class MatchResult(BaseModel):
    product_id: UUID | None = None
    product_sku: str | None = None
    product_name: str | None = None
    confidence: float
    match_type: str
    needs_review: bool
    pack_qty: int = 1  # Количество в упаковке
