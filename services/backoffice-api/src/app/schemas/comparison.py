"""Schemas API del comparador comercial."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CompetitorOut(BaseModel):
    id: UUID
    name: str
    brand: str | None = None
    is_internal: bool = False
    linked_product_id: UUID | None = None


class CompetitorCreate(BaseModel):
    name: str
    brand: str | None = None
    is_internal: bool = False
    linked_product_id: UUID | None = None


class CompetitorListResponse(BaseModel):
    items: list[CompetitorOut]
    page: int
    page_size: int
    total: int


class ComparisonSetOut(BaseModel):
    id: UUID
    subject_product_id: UUID
    completeness_status: str
    published_version: int
    source_document_id: UUID | None = None


class ImportComparisonOut(BaseModel):
    imported_rows: int
    gaps_created: int
    columns: int


class PublishComparisonOut(BaseModel):
    published_version: int


class ComparisonColumnOut(BaseModel):
    column_key: str
    header_label: str
    sort_order: int
    display_tier: int
    is_priority: bool


class ComparisonColumnListResponse(BaseModel):
    items: list[ComparisonColumnOut]


class ComparisonColumnPriorityUpdate(BaseModel):
    priority_column_keys: list[str]
