"""Productos y aliases (spec 003)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: UUID
    name: str
    brand: str = "Biomont"
    duration_type: str | None = None
    description: str | None = None
    country_iso: str | None = Field(default=None, min_length=2, max_length=2)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductAlias(BaseModel):
    id: UUID
    product_id: UUID
    alias: str
    normalized_alias: str
    source: str = "manual"
    confidence: float = 1.0


class ProductCandidate(BaseModel):
    """Resultado de resolucion: producto + score de similitud."""

    product_id: UUID
    product_name: str
    alias_matched: str
    similarity: float = Field(ge=0.0, le=1.0)
