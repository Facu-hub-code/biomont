from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class ProductBasePayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    brand: str = Field(default="Biomont", min_length=1, max_length=255)
    duration_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    country_iso: str | None = Field(default=None, min_length=2, max_length=2)


class ProductCreate(ProductBasePayload):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    brand: str | None = Field(default=None, min_length=1, max_length=255)
    duration_type: str | None = Field(default=None, max_length=120)
    description: str | None = None
    country_iso: str | None = Field(default=None, min_length=2, max_length=2)


class ProductOut(BaseModel):
    id: UUID
    name: str
    brand: str
    duration_type: str | None = None
    description: str | None = None
    country_iso: str | None = None
    alias_count: int = 0
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=255)
    source: str = Field(default="manual", min_length=1, max_length=30)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ProductAliasUpdate(BaseModel):
    alias: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = Field(default=None, min_length=1, max_length=30)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ProductAliasOut(BaseModel):
    id: UUID
    product_id: UUID
    alias: str
    normalized_alias: str
    source: str
    confidence: float
    created_at: datetime


ProductListResponse = PaginatedResponse[ProductOut]
ProductAliasListResponse = PaginatedResponse[ProductAliasOut]
