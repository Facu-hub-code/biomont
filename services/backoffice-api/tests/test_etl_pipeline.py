"""Test del ETL con mocks de docling y embeddings (spec 003).

Cubre el nuevo flujo: legacy chunks + sections + knowledge_chunks +
faq_entries por kind, manteniendo idempotencia y `mark_failed` en error.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from biomont_common.db.rag_repository import ChunkInput, KnowledgeChunkInput
from biomont_common.integrations.faq_extractor import FaqPair

from app.services.etl_pipeline import DocumentIngestService
from app.db.document_repository import SectionInput


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
        self.sections: dict[uuid.UUID, list[SectionInput]] = {}

    async def find_by_content_sha256(self, _sha: str):
        return None

    async def create_pending(
        self,
        *,
        title: str,
        product_name,
        country_iso,
        language,
        source_filename,
        content_sha256,
        uploaded_by,
        kind: str = "bitacora",
        product_id=None,
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

    async def mark_processing(self, doc_id) -> None:
        ...

    async def delete_sections(self, _conn, _doc_id) -> None:
        ...

    async def insert_sections(self, _conn, doc_id, sections) -> dict:
        self.sections[doc_id] = list(sections)
        return {s.section_index: uuid.uuid4() for s in sections}


class FakeRagRepository:
    def __init__(self) -> None:
        self.legacy_inserts: list[ChunkInput] = []
        self.knowledge_inserts: list[KnowledgeChunkInput] = []

    async def insert_chunks(self, _conn, _doc_id, chunks):
        self.legacy_inserts.extend(list(chunks))

    async def delete_chunks_for_document(self, _conn, _doc_id) -> None:
        ...

    async def insert_knowledge_chunks(self, _conn, _doc_id, chunks):
        self.knowledge_inserts.extend(list(chunks))

    async def delete_knowledge_chunks_for_document(self, _conn, _doc_id) -> None:
        ...


class FakeFaqRepository:
    def __init__(self) -> None:
        self.inserts: list[Any] = []

    async def delete_for_document(self, _conn, _doc_id) -> None:
        ...

    async def insert_many(self, _conn, entries) -> int:
        items = list(entries)
        self.inserts.extend(items)
        return len(items)


class FakePool:
    @asynccontextmanager
    async def transaction(self):
        yield object()

    @asynccontextmanager
    async def acquire(self):
        yield object()


class FakeBitacoraConverter:
    """Devuelve markdown que matchea el formato bitacora (`N°` + `N.M`)."""

    def convert_to_markdown(self, _pdf_path: Path) -> str:
        return (
            "1° GENERALIDADES DEL PRINCIPIO ACTIVO\n\n"
            "Texto general del producto.\n\n"
            "1.1 Mecanismo de accion\n\n"
            "10 mg/kg cada 12 semanas en perros.\n\n"
            "2° INTERACCIONES MEDICAMENTOSAS\n\n"
            "Sin interacciones reportadas.\n"
        )


class FakeFichaConverter:
    def convert_to_markdown(self, _pdf_path: Path) -> str:
        return (
            "1. NOMBRE COMERCIAL DEL PRODUCTO\n\n"
            "Proteggo 3M.\n\n"
            "2. DOSIFICACION\n\n"
            "Peso corporal kg verde 1400 mg. 25-56 mg/kg via oral.\n\n"
            "3. CONTRAINDICACIONES\n\n"
            "No usar en menores de 8 semanas.\n"
        )


class FakeBalotarioConverter:
    def convert_to_markdown(self, _pdf_path: Path) -> str:
        return (
            "Balotario.\n\n"
            "• ¿Puede usarse en gestacion?\n\n"
            "Si, hay estudios de seguridad demostrados en perras gestantes.\n\n"
            "• ¿Cual es la dosis?\n\n"
            "10 mg/kg cada 12 semanas.\n"
        )


class FakeEmbeddings:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]


@dataclass
class FakeFaqExtractor:
    pairs: list[FaqPair] = field(default_factory=list)

    async def extract(self, _markdown: str) -> list[FaqPair]:
        return list(self.pairs)


@pytest.mark.asyncio
async def test_ingest_bitacora_persists_legacy_and_knowledge_chunks() -> None:
    documents = FakeDocumentRepository()
    rag = FakeRagRepository()
    pipeline = DocumentIngestService(
        pool=FakePool(),  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        rag=rag,  # type: ignore[arg-type]
        converter=FakeBitacoraConverter(),
        embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
    )

    result = await pipeline.ingest_pdf(
        pdf_bytes=b"%PDF-fake",
        original_filename="bitacora.pdf",
        title="Bitacora Proteggo",
        product_name=None,
        country_iso=None,
        language="es",
        uploaded_by=uuid.uuid4(),
        kind="bitacora",
    )

    assert result.chunks_persisted > 0
    assert result.knowledge_chunks_persisted > 0
    assert result.sections_persisted >= 3
    assert documents.rows[result.document_id].markdown
    assert documents.failed == {}


@pytest.mark.asyncio
async def test_ingest_balotario_invokes_faq_extractor() -> None:
    documents = FakeDocumentRepository()
    rag = FakeRagRepository()
    faqs = FakeFaqRepository()
    extractor = FakeFaqExtractor(
        pairs=[
            FaqPair(
                question="Puede usarse en gestacion?",
                answer="Si, hay estudios de seguridad.",
            ),
            FaqPair(
                question="Cual es la dosis?",
                answer="10 mg/kg cada 12 semanas.",
            ),
        ]
    )
    pipeline = DocumentIngestService(
        pool=FakePool(),  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        rag=rag,  # type: ignore[arg-type]
        converter=FakeBalotarioConverter(),
        embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
        faq_repository=faqs,  # type: ignore[arg-type]
        faq_extractor=extractor,
    )

    result = await pipeline.ingest_pdf(
        pdf_bytes=b"%PDF-balotario",
        original_filename="balotario.pdf",
        title="Balotario Proteggo",
        product_name="Proteggo 3M",
        country_iso=None,
        language="es",
        uploaded_by=uuid.uuid4(),
        kind="balotario",
    )

    assert result.faq_entries_persisted == 2
    assert len(faqs.inserts) == 2
    assert result.knowledge_chunks_persisted > 0


@pytest.mark.asyncio
async def test_ingest_ficha_tecnica_chunks_with_structure() -> None:
    documents = FakeDocumentRepository()
    rag = FakeRagRepository()
    pipeline = DocumentIngestService(
        pool=FakePool(),  # type: ignore[arg-type]
        documents=documents,  # type: ignore[arg-type]
        rag=rag,  # type: ignore[arg-type]
        converter=FakeFichaConverter(),
        embeddings=FakeEmbeddings(),  # type: ignore[arg-type]
    )

    result = await pipeline.ingest_pdf(
        pdf_bytes=b"%PDF-ficha",
        original_filename="ficha.pdf",
        title="Ficha Proteggo",
        product_name=None,
        country_iso=None,
        language="es",
        uploaded_by=uuid.uuid4(),
        kind="ficha_tecnica",
    )

    section_types = {c.section_type for c in rag.knowledge_inserts}
    assert "dosing_table" in section_types
    assert "contraindications" in section_types


@pytest.mark.asyncio
async def test_ingest_marks_failed_when_no_content() -> None:
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
            kind="bitacora",
        )

    assert documents.failed
