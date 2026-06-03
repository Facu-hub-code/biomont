"""Schemas del comparador comercial (spec 012)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class Competitor(BaseModel):
    id: UUID
    name: str
    brand: str | None = None
    is_internal: bool = False
    linked_product_id: UUID | None = None


class ComparisonColumn(BaseModel):
    column_key: str
    header_label: str
    sort_order: int = 0


class ComparisonRow(BaseModel):
    id: UUID
    display_name: str
    is_subject: bool = False
    competitor_id: UUID | None = None
    linked_product_id: UUID | None = None
    cells: dict[str, str | None] = Field(default_factory=dict)


class ComparisonDiffItem(BaseModel):
    column_key: str
    header_label: str
    subject_value: str
    competitor_value: str
    sort_order: int = 0


class ComparisonDiffResult(BaseModel):
    subject_product_id: UUID
    subject_name: str
    competitor_name: str
    published_version: int
    differences: list[ComparisonDiffItem]


class ComparisonRedactorItem(BaseModel):
    column_key: str
    header_label: str
    tier: int
    subject_snippet: str
    competitor_snippet: str
    truncated: bool = False


class ComparisonRedactorInput(BaseModel):
    subject_name: str
    competitor_name: str
    published_version: int
    presentation_mode: str  # summary | focus | full
    focus_column_key: str | None = None
    highlight_items: list[ComparisonRedactorItem]
    items: list[ComparisonRedactorItem]
    other_items_count: int


class ComparisonRedactorBullet(BaseModel):
    column_key: str
    text: str


class ComparisonRedactorOutput(BaseModel):
    opening: str
    bullets: list[ComparisonRedactorBullet]
    closing_hint: str | None = None
    footer: str
