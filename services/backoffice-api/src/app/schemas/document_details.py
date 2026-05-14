from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginatedResponse


class DocumentSectionOut(BaseModel):
    id: UUID
    document_id: UUID
    section_index: int
    parent_section_id: UUID | None = None
    section_number: str | None = None
    section_title: str | None = None
    section_kind: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    raw_text: str | None = None
    created_at: datetime


class DocumentKnowledgeChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    section_id: UUID | None = None
    product_id: UUID | None = None
    kind: str
    chunk_index: int
    section_type: str | None = None
    subsection_type: str | None = None
    topic: str | None = None
    content: str
    token_count: int
    contains_table: bool
    contains_dose: bool
    species: list[str]
    metadata: dict[str, Any]
    created_at: datetime


class DocumentLegacyChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, Any]
    created_at: datetime


class DocumentFaqEntryOut(BaseModel):
    id: UUID
    product_id: UUID | None = None
    document_id: UUID
    question: str
    answer: str
    source_page: int | None = None
    created_at: datetime


DocumentSectionListResponse = PaginatedResponse[DocumentSectionOut]
DocumentKnowledgeChunkListResponse = PaginatedResponse[DocumentKnowledgeChunkOut]
DocumentLegacyChunkListResponse = PaginatedResponse[DocumentLegacyChunkOut]
DocumentFaqEntryListResponse = PaginatedResponse[DocumentFaqEntryOut]
