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
    display_tier: int = 3


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
    display_tier: int = 3


class ComparisonSimilarityItem(BaseModel):
    column_key: str
    header_label: str
    shared_value: str
    sort_order: int = 0
    display_tier: int = 3


class ComparisonDiffResult(BaseModel):
    subject_product_id: UUID
    subject_name: str
    competitor_name: str
    published_version: int
    differences: list[ComparisonDiffItem]
    similarities: list[ComparisonSimilarityItem] = Field(default_factory=list)


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
    similarity_items: list[ComparisonRedactorItem] = Field(default_factory=list)
    other_items_count: int


class ComparisonRedactorBullet(BaseModel):
    column_key: str
    text: str


class ComparisonRedactorOutput(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)
    opening: str = ""
    bullets: list[ComparisonRedactorBullet] = Field(default_factory=list)
    follow_up_hint: str | None = None
    closing_hint: str | None = None
    footer: str
