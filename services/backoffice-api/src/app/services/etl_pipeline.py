"""Pipeline ETL: PDF -> markdown -> chunks -> embeddings -> Postgres.

No accede directo a docling ni a OpenAI: recibe ambos colaboradores como
dependencias, para poder mockearlos en tests (cumple
`.cursor/rules/testing-policy-python.mdc`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from langchain_core.embeddings import Embeddings

from biomont_common.db.pool import DatabasePool
from biomont_common.db.rag_repository import ChunkInput, RagRepository
from biomont_common.integrations.text_splitter import MarkdownChunker, TextChunk
from biomont_common.logging import get_logger

from app.db.document_repository import DocumentRepository, compute_sha256
from app.integrations.docling_converter import PdfToMarkdownConverter

_logger = get_logger("etl.pipeline")


@dataclass(slots=True)
class IngestResult:
    document_id: UUID
    chunks_persisted: int
    markdown_chars: int


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
    ) -> None:
        self._pool = pool
        self._documents = documents
        self._rag = rag
        self._converter = converter
        self._embeddings = embeddings
        self._chunker = chunker or MarkdownChunker()

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
    ) -> IngestResult:
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

        document_id = await self._documents.create_pending(
            title=title,
            product_name=product_name,
            country_iso=country_iso,
            language=language,
            source_filename=original_filename,
            content_sha256=sha,
            uploaded_by=uploaded_by,
        )

        try:
            markdown = self._convert_pdf(pdf_bytes, original_filename)
            chunks = self._chunker.split(markdown)
            if not chunks:
                raise RuntimeError("docling no produjo contenido extraible")

            embeddings = await self._embed_chunks(chunks)

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
                        for chunk, vector in zip(chunks, embeddings, strict=True)
                    ],
                )

            await self._documents.mark_validated(
                document_id,
                markdown=markdown,
                validated_by=uploaded_by,
            )
            _logger.info(
                "etl_ingested_document",
                action="ingest",
                document_id=str(document_id),
                chunks=len(chunks),
            )
            return IngestResult(
                document_id=document_id,
                chunks_persisted=len(chunks),
                markdown_chars=len(markdown),
            )
        except Exception as exc:
            await self._documents.mark_failed(document_id, str(exc))
            _logger.exception(
                "etl_ingest_failed",
                action="ingest_failed",
                document_id=str(document_id),
            )
            raise

    def _convert_pdf(self, pdf_bytes: bytes, original_filename: str | None) -> str:
        import tempfile

        suffix = Path(original_filename or "doc.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            markdown = self._converter.convert_to_markdown(Path(tmp.name))
        return markdown.strip()

    async def _embed_chunks(self, chunks: Iterable[TextChunk]) -> list[list[float]]:
        texts = [chunk.content for chunk in chunks]
        if not texts:
            return []
        return await self._embeddings.aembed_documents(texts)
