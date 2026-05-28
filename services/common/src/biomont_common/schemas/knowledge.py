"""Knowledge chunks y document kinds (spec 003)."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    """Tipos de documento alineados con el enum SQL `document_kind`."""

    ficha_tecnica = "ficha_tecnica"
    bitacora = "bitacora"
    balotario = "balotario"


class HybridChunkHit(BaseModel):
    """Chunk recuperado por el retriever hibrido."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    product_id: UUID | None = None
    kind: DocumentKind
    chunk_index: int
    section_type: str | None = None
    content: str
    country_iso: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    final_score: float = Field(ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)

