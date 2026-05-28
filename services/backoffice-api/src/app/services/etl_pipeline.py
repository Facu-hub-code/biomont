"""Pipeline ETL: PDF -> markdown -> chunks -> embeddings -> Postgres.

Produce `document_sections` + `knowledge_chunks` enriquecidos (chunker
estructural parametrizado por `DocumentKind`). Es la unica salida de
vectorizacion consumida por el grafo hibrido del agente (spec 007).

No hace I/O directo: recibe `converter`, `embeddings` y chunkers como
dependencias para poder testearlos con mocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from langchain_core.embeddings import Embeddings

from biomont_common.db.document_product_repository import DocumentProductRepository
from biomont_common.db.pool import DatabasePool
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import KnowledgeChunkInput, RagRepository
from biomont_common.integrations.text_splitter import (
    StructuredChunkerError,
    StructuredMarkdownChunker,
)
from biomont_common.logging import get_logger
from biomont_common.schemas.knowledge import DocumentKind

from biomont_common.settings import get_rag_settings

from app.db.document_repository import (
    DocumentRepository,
    SectionInput,
    compute_sha256,
)
from app.integrations.docling_converter import PdfToMarkdownConverter

_logger = get_logger("etl.pipeline")

_FAIL_REASON_MAX_LEN = 8_192


@dataclass(slots=True)
class IngestResult:
    document_id: UUID
    knowledge_chunks_persisted: int = 0
    sections_persisted: int = 0
    markdown_chars: int = 0


class DocumentIngestService:
    """Orquesta el ingreso de un PDF al store de RAG."""

    def __init__(
        self,
        *,
        pool: DatabasePool,
        documents: DocumentRepository,
        rag: RagRepository,
        converter: PdfToMarkdownConverter,
        embeddings: Embeddings,
        structured_chunker: StructuredMarkdownChunker | None = None,
        product_repository: ProductRepository | None = None,
        document_products: DocumentProductRepository | None = None,
    ) -> None:
        self._pool = pool
        self._documents = documents
        self._rag = rag
        self._converter = converter
        self._embeddings = embeddings
        if structured_chunker is None:
            r = get_rag_settings()
            self._structured_chunker = StructuredMarkdownChunker(
                chunk_tokens=r.knowledge_chunk_tokens,
                overlap_tokens=r.knowledge_chunk_overlap,
            )
        else:
            self._structured_chunker = structured_chunker
        self._product_repository = product_repository
        self._document_products = document_products

    async def ingest_pdf(
        self,
        *,
        pdf_bytes: bytes,
        original_filename: str | None,
        title: str,
        product_name: str | None,
        country_iso: str | None,
        language: str,
        uploaded_by: UUID,
        kind: str = "bitacora",
        product_id: UUID | None = None,
        product_ids: list[UUID] | None = None,
    ) -> IngestResult:
        document_kind = DocumentKind(kind)
        sha = compute_sha256(pdf_bytes)
        existing = await self._documents.find_by_content_sha256(sha)
        if existing is not None:
            _logger.info(
                "etl_duplicate_document",
                action="duplicate",
                document_id=str(existing.id),
            )
            return IngestResult(
                document_id=existing.id,
                knowledge_chunks_persisted=existing.chunk_count,
                markdown_chars=len(existing.markdown or ""),
            )

        linked_ids = list(dict.fromkeys(product_ids or []))
        resolved_product_id = product_id
        if resolved_product_id and resolved_product_id not in linked_ids:
            linked_ids.insert(0, resolved_product_id)
        elif resolved_product_id is None and linked_ids:
            resolved_product_id = linked_ids[0]

        if (
            not linked_ids
            and resolved_product_id is None
            and self._product_repository is not None
            and product_name
        ):
            candidates = await self._product_repository.search_candidates(
                product_name,
                allowed_countries=[country_iso] if country_iso else None,
                limit=1,
            )
            if candidates and candidates[0].similarity >= 0.95:
                resolved_product_id = candidates[0].product_id
                linked_ids = [resolved_product_id]

        document_id = await self._documents.create_pending(
            title=title,
            product_name=product_name,
            country_iso=country_iso,
            language=language,
            source_filename=original_filename,
            content_sha256=sha,
            uploaded_by=uploaded_by,
            kind=document_kind.value,
            product_id=resolved_product_id,
        )

        if self._document_products is not None and linked_ids:
            await self._document_products.replace_for_document(
                document_id=document_id,
                product_ids=linked_ids,
                primary_product_id=resolved_product_id,
                created_by=uploaded_by,
            )

        try:
            result = await self._do_ingest(
                document_id=document_id,
                pdf_bytes=pdf_bytes,
                original_filename=original_filename,
                language=language,
                uploaded_by=uploaded_by,
                kind=document_kind,
                product_id=resolved_product_id,
            )
            _logger.info(
                "etl_ingested_document",
                action="ingest",
                document_id=str(document_id),
                kind=document_kind.value,
                knowledge_chunks=result.knowledge_chunks_persisted,
                sections=result.sections_persisted,
            )
            return result
        except Exception as exc:
            reason = str(exc)
            if len(reason) > _FAIL_REASON_MAX_LEN:
                reason = reason[: _FAIL_REASON_MAX_LEN] + "…(truncado)"
            await self._documents.mark_failed(document_id, reason)
            _logger.exception(
                "etl_ingest_failed",
                action="ingest_failed",
                document_id=str(document_id),
                kind=document_kind.value,
            )
            raise

    async def reingest_existing(
        self,
        *,
        document_id: UUID,
        pdf_bytes: bytes,
        original_filename: str | None,
        kind: str,
        product_id: UUID | None,
        validated_by: UUID,
        language: str = "es",
    ) -> IngestResult:
        """Reingesta un documento ya existente."""

        await self._documents.mark_processing(document_id)
        document_kind = DocumentKind(kind)
        return await self._do_ingest(
            document_id=document_id,
            pdf_bytes=pdf_bytes,
            original_filename=original_filename,
            language=language,
            uploaded_by=validated_by,
            kind=document_kind,
            product_id=product_id,
        )

    async def _do_ingest(
        self,
        *,
        document_id: UUID,
        pdf_bytes: bytes,
        original_filename: str | None,
        language: str,
        uploaded_by: UUID,
        kind: DocumentKind,
        product_id: UUID | None,
    ) -> IngestResult:
        markdown = self._convert_pdf(pdf_bytes, original_filename)
        if not markdown.strip():
            raise RuntimeError("docling no produjo contenido extraible")

        try:
            structured = self._structured_chunker.split(markdown, kind=kind)
        except StructuredChunkerError:
            raise

        if not structured.chunks:
            raise RuntimeError("el chunker estructural no produjo fragmentos")

        structured_embeddings = await self._embed_documents(
            [c.content for c in structured.chunks]
        )

        async with self._pool.transaction() as conn:
            await self._documents.delete_sections(conn, document_id)
            section_inputs = [
                SectionInput(
                    section_index=s.index,
                    section_number=s.number,
                    section_title=s.title,
                    section_kind=s.kind,
                    parent_index=s.parent_index,
                    raw_text=s.raw_text,
                )
                for s in structured.sections
            ]
            section_map = await self._documents.insert_sections(
                conn, document_id, section_inputs
            )

            await self._rag.delete_knowledge_chunks_for_document(conn, document_id)
            knowledge_inputs = [
                KnowledgeChunkInput(
                    index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding=vector,
                    kind=kind,
                    section_id=section_map.get(chunk.section_index),
                    product_id=product_id,
                    section_type=chunk.section_type,
                    subsection_type=chunk.subsection_type,
                    topic=chunk.topic,
                    contains_table=chunk.contains_table,
                    contains_dose=chunk.contains_dose,
                    species=tuple(chunk.species),
                    metadata_json=json.dumps(chunk.metadata),
                )
                for chunk, vector in zip(
                    structured.chunks, structured_embeddings, strict=True
                )
            ]
            await self._rag.insert_knowledge_chunks(
                conn, document_id, knowledge_inputs
            )

        await self._documents.mark_validated(
            document_id,
            markdown=markdown,
            validated_by=uploaded_by,
        )

        return IngestResult(
            document_id=document_id,
            knowledge_chunks_persisted=len(structured.chunks),
            sections_persisted=len(structured.sections),
            markdown_chars=len(markdown),
        )

    def _convert_pdf(self, pdf_bytes: bytes, original_filename: str | None) -> str:
        import tempfile

        suffix = Path(original_filename or "doc.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            markdown = self._converter.convert_to_markdown(Path(tmp.name))
        return markdown.strip()

    async def _embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        batch = list(texts)
        if not batch:
            return []
        return await self._embeddings.aembed_documents(batch)


__all__ = [
    "DocumentIngestService",
    "IngestResult",
]
