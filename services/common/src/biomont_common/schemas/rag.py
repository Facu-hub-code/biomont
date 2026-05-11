"""Contratos para el flujo RAG (compartidos entre agente y backoffice)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Chunk recuperado por el retriever, con su similitud."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    country_iso: str | None = None
    chunk_index: int
    content: str
    similarity: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    """Cita que el agente debe entregar junto con la respuesta."""

    document_id: UUID
    document_title: str
    similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Similitud coseno reportada al usuario.",
    )


class RagAnswer(BaseModel):
    """Salida estructurada que se le exige al LLM."""

    answer: str = Field(
        min_length=1,
        description="Respuesta final para el usuario en su idioma.",
    )
    citations: list[Citation] = Field(
        min_length=1,
        description="Al menos una cita es obligatoria.",
    )
