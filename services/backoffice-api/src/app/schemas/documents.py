from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DocumentStatus = Literal[
    "draft", "processing", "validated", "archived", "failed"
]


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    product_name: str | None
    country_iso: str | None
    language: str
    status: DocumentStatus
    classification: dict
    uploaded_by: UUID | None
    validated_by: UUID | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class DocumentDetail(DocumentSummary):
    markdown: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    product_name: str | None = None
    country_iso: str | None = Field(default=None, min_length=2, max_length=2)
    language: str | None = Field(default=None, min_length=2, max_length=2)
    status: DocumentStatus | None = None
    classification: dict | None = None
