from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DocumentStatus = Literal[
    "draft", "processing", "validated", "archived", "failed"
]

DocumentKindLiteral = Literal["ficha_tecnica", "bitacora", "balotario"]


class DocumentLinkedProductBrief(BaseModel):
    product_id: UUID
    name: str
    is_primary: bool = False


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
    kind: DocumentKindLiteral = "bitacora"
    product_id: UUID | None = None
    linked_products: list[DocumentLinkedProductBrief] = Field(default_factory=list)
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
    kind: DocumentKindLiteral | None = None
    product_id: UUID | None = None


class ReingestResponse(BaseModel):
    document_id: UUID
    knowledge_chunks: int
    sections: int
    markdown_chars: int
