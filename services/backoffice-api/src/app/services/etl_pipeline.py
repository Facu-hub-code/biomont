"""Pipeline ETL: PDF -> markdown -> chunks -> embeddings -> Postgres.

A partir de la spec 003 el pipeline produce simultaneamente:

- `document_chunks` legacy (chunker basado en headers + tokens). Conservado
  para el camino flag-off (AGENT_USE_GRAPH=false) y para evitar romper
  retrievers en uso.
- `document_sections` + `knowledge_chunks` enriquecidos (chunker estructural
  parametrizado por `DocumentKind`). Estos son los que consume el grafo
  hibrido vec+BM25.
- `faq_entries` cuando el documento es balotario (extractor LLM una vez por
  documento). Si la extraccion falla, el ingest no aborta: el balotario
  queda chunkificado normalmente y el FAQ retriever fallback al hibrido.

No hace I/O directo: recibe `converter`, `embeddings`, `chunkers` y el
extractor de FAQ como dependencias para poder testearlos con mocks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from langchain_core.embeddings import Embeddings

from biomont_common.db.document_product_repository import DocumentProductRepository
from biomont_common.db.faq_repository import FaqInput, FaqRepository
from biomont_common.db.pool import DatabasePool
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import (
    ChunkInput,
    KnowledgeChunkInput,
    RagRepository,
)
from biomont_common.integrations.faq_extractor import (
    FaqExtractor,
    FaqExtractorError,
    FaqExtractorProtocol,
)
from biomont_common.integrations.text_splitter import (
    MarkdownChunker,
    StructuredChunkerError,
    StructuredMarkdownChunker,
    TextChunk,
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
    chunks_persisted: int
    knowledge_chunks_persisted: int = 0
    sections_persisted: int = 0
    faq_entries_persisted: int = 0
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
        chunker: MarkdownChunker | None = None,
        structured_chunker: StructuredMarkdownChunker | None = None,
        faq_repository: FaqRepository | None = None,
        faq_extractor: FaqExtractorProtocol | None = None,
        product_repository: ProductRepository | None = None,
        document_products: DocumentProductRepository | None = None,
    ) -> None:
        self._pool = pool
        self._documents = documents
        self._rag = rag
        self._converter = converter
        self._embeddings = embeddings
        self._chunker = chunker or MarkdownChunker()
        if structured_chunker is None:
            r = get_rag_settings()
            self._structured_chunker = StructuredMarkdownChunker(
                chunk_tokens=r.knowledge_chunk_tokens,
                overlap_tokens=r.knowledge_chunk_overlap,
            )
        else:
            self._structured_chunker = structured_chunker
        self._faq_repository = faq_repository
        self._faq_extractor = faq_extractor
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
                chunks_persisted=existing.chunk_count,
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
                legacy_chunks=result.chunks_persisted,
                knowledge_chunks=result.knowledge_chunks_persisted,
                sections=result.sections_persisted,
                faq_entries=result.faq_entries_persisted,
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
        """Reingesta un documento ya existente con el nuevo schema spec 003.

        Util para migrar documentos del corpus actual sin re-uploadear.
        """

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

    # ------------------------------------------------------------------
    # internos
    # ------------------------------------------------------------------

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

        legacy_chunks = self._chunker.split(markdown)
        if not legacy_chunks:
            raise RuntimeError("docling no produjo contenido extraible")

        try:
            structured = self._structured_chunker.split(markdown, kind=kind)
        except StructuredChunkerError:
            # No tenemos estructura -> falla explicita; sin estructura el
            # grafo no puede filtrar por section_type y degradaria silenciosamente.
            raise

        legacy_embeddings = await self._embed_chunks(legacy_chunks)
        structured_embeddings = await self._embed_documents(
            [c.content for c in structured.chunks]
        )

        faq_entries: list[FaqInput] = []
        if (
            kind == DocumentKind.balotario
            and self._faq_extractor is not None
            and self._faq_repository is not None
        ):
            try:
                faq_pairs = await self._faq_extractor.extract(markdown)
            except FaqExtractorError as exc:
                _logger.warning(
                    "etl_faq_extractor_skipped",
                    action="faq_extract_failed",
                    document_id=str(document_id),
                    error=str(exc)[:200],
                )
                faq_pairs = []
            if faq_pairs:
                faq_texts = [f"{p.question}\n{p.answer}" for p in faq_pairs]
                faq_vectors = await self._embed_documents(faq_texts)
                for pair, vector in zip(faq_pairs, faq_vectors, strict=True):
                    faq_entries.append(
                        FaqInput(
                            product_id=product_id,
                            document_id=document_id,
                            question=pair.question,
                            answer=pair.answer,
                            embedding=vector,
                            source_page=pair.source_page,
                        )
                    )

        async with self._pool.transaction() as conn:
            await self._rag.delete_chunks_for_document(conn, document_id)
            await self._rag.insert_chunks(
                conn,
                document_id,
                [
                    ChunkInput(
                        index=chunk.index,
                        content=chunk.content,
                        token_count=chunk.token_count,
                        metadata_json=json.dumps(chunk.metadata),
                        embedding=vector,
                    )
                    for chunk, vector in zip(
                        legacy_chunks, legacy_embeddings, strict=True
                    )
                ],
            )

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

            if self._faq_repository is not None and kind == DocumentKind.balotario:
                await self._faq_repository.delete_for_document(conn, document_id)
            if faq_entries and self._faq_repository is not None:
                await self._faq_repository.insert_many(conn, faq_entries)

        await self._documents.mark_validated(
            document_id,
            markdown=markdown,
            validated_by=uploaded_by,
        )

        return IngestResult(
            document_id=document_id,
            chunks_persisted=len(legacy_chunks),
            knowledge_chunks_persisted=len(structured.chunks),
            sections_persisted=len(structured.sections),
            faq_entries_persisted=len(faq_entries),
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

    async def _embed_chunks(
        self, chunks: Iterable[TextChunk]
    ) -> list[list[float]]:
        texts = [chunk.content for chunk in chunks]
        if not texts:
            return []
        return await self._embeddings.aembed_documents(texts)

    async def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embeddings.aembed_documents(texts)


# Re-export FaqExtractor para compatibilidad de imports en tests.
__all__ = [
    "DocumentIngestService",
    "FaqExtractor",
    "IngestResult",
]