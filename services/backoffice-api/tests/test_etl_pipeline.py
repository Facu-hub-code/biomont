"""Test del ETL con mocks de docling y embeddings."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from biomont_common.db.rag_repository import ChunkInput

from app.services.etl_pipeline import DocumentIngestService


@dataclass(slots=True)
class _FakeDocumentRow:
    id: uuid.UUID
    title: str
    markdown: str | None
    chunk_count: int


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, _FakeDocumentRow] = {}
        self.failed: dict[uuid.UUID, str] = {}

    async def find_by_content_sha256(self, _sha: str):
        return None

    async def create_pending(
        self, *, title: str, product_name, country_iso, language,
        source_filename, content_sha256, uploaded_by,
    ) -> uuid.UUID:
        new_id = uuid.uuid4()
        self.rows[new_id] = _FakeDocumentRow(
            id=new_id, title=title, markdown=None, chunk_count=0,
        )
        return new_id

    async def mark_validated(self, doc_id, *, markdown, validated_by) -> None:
        row = self.rows[doc_id]
        row.markdown = markdown

    async def mark_failed(self, doc_id, reason: str) -> None:
        self.failed[doc_id] = reason


class FakeRagRepository:
    def __init__(self) -> None:
        self.inserts: list[ChunkInput] = []

    async def insert_chunks(self, _conn, _doc_id, chunks):
        self.inserts.extend(list(chunks))

    async def delete_chunks_for_document(self, _conn, _doc_id) -> None:
        ...


class FakePool:
    @asynccontextmanager
    async def transaction(self):
        yield object()

    @asynccontextmanager
    async def acquire(self):
        yield object()


class FakeConverter:
    def convert_to_markdown(self, _pdf_path: Path) -> str:
        return (
            "# Producto X\n\n"
            "## Dosis\n\n"
            "0.2 mg/kg via subcutanea.\n\n"
            "## Contraindicacion\n\n"
            "Animales gestantes.\n"
        )


class FakeEmbeddings:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]


@pytest.mark.asyncio
async def test_ingest_pipeline_persists_chunks_and_validates() -> None:
    documents = FakeDocumentRepository()
    rag = FakeRagRepository()
    pipeline = DocumentIngestService(
        pool=FakePool(),  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        rag=rag,  # type: ignore[arg-type]
        converter=FakeConverter(),
        embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
    )

    result = await pipeline.ingest_pdf(
        pdf_bytes=b"%PDF-fake",
        original_filename="ficha.pdf",
        title="Ficha producto X",
        product_name="Producto X",
        country_iso="PE",
        language="es",
        uploaded_by=uuid.uuid4(),
    )

    assert result.chunks_persisted > 0
    assert result.chunks_persisted == len(rag.inserts)
    assert documents.rows[result.document_id].markdown
    assert documents.failed == {}


@pytest.mark.asyncio
async def test_ingest_pipeline_marks_failed_when_no_content() -> None:
    documents = FakeDocumentRepository()

    class EmptyConverter:
        def convert_to_markdown(self, _pdf_path: Path) -> str:
            return ""

    pipeline = DocumentIngestService(
        pool=FakePool(),  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        rag=FakeRagRepository(),  # type: ignore[arg-type]
        converter=EmptyConverter(),
        embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
    )

    with pytest.raises(Exception):
        await pipeline.ingest_pdf(
            pdf_bytes=b"%PDF-empty",
            original_filename="x.pdf",
            title="X",
            product_name=None,
            country_iso=None,
            language="es",
            uploaded_by=uuid.uuid4(),
        )

    assert documents.failed, "el documento deberia quedar marcado como failed"
