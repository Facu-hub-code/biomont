"""Persistencia de `documents` (sin chunks; estos viven en RagRepository).

A partir de la spec 003 tambien gestiona `document_sections` (estructura
jerarquica del documento, alimentada por `StructuredMarkdownChunker`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class DocumentRow:
    id: UUID
    title: str
    product_name: str | None
    country_iso: str | None
    language: str
    status: str
    source_filename: str | None
    content_sha256: str | None
    markdown: str | None
    classification: dict[str, Any]
    uploaded_by: UUID | None
    validated_by: UUID | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    kind: str = "bitacora"
    product_id: UUID | None = None
    chunk_count: int = 0


@dataclass(slots=True)
class SectionInput:
    """Seccion estructural detectada por el parser (spec 003)."""

    section_index: int
    section_number: str | None
    section_title: str | None
    section_kind: str | None
    parent_index: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    raw_text: str | None = None


@dataclass(slots=True)
class DocumentSectionRow:
    id: UUID
    document_id: UUID
    section_index: int
    parent_section_id: UUID | None
    section_number: str | None
    section_title: str | None
    section_kind: str | None
    page_start: int | None
    page_end: int | None
    raw_text: str | None
    created_at: datetime


@dataclass(slots=True)
class DocumentKnowledgeChunkRow:
    id: UUID
    document_id: UUID
    section_id: UUID | None
    product_id: UUID | None
    kind: str
    chunk_index: int
    section_type: str | None
    subsection_type: str | None
    topic: str | None
    content: str
    token_count: int
    contains_table: bool
    contains_dose: bool
    species: list[str]
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(slots=True)
class DocumentLegacyChunkRow:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(slots=True)
class DocumentFaqEntryRow:
    id: UUID
    product_id: UUID | None
    document_id: UUID
    question: str
    answer: str
    source_page: int | None
    created_at: datetime


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class DocumentRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_documents(self) -> list[DocumentRow]:
        # Sin `markdown`: evita cargar megabytes por fila (lista del backoffice);
        # el detalle usa `get_document`.
        query = """
            SELECT d.id,
                   d.title,
                   d.product_name,
                   d.country_iso,
                   d.language,
                   d.status,
                   d.source_filename,
                   d.content_sha256,
                   d.classification,
                   d.uploaded_by,
                   d.validated_by,
                   d.validated_at,
                   d.created_at,
                   d.updated_at,
                   d.kind,
                   d.product_id,
                   COALESCE(c.cnt, 0) AS chunk_count
            FROM public.documents d
            LEFT JOIN (
                SELECT document_id, count(*) AS cnt
                FROM public.document_chunks
                GROUP BY document_id
            ) c ON c.document_id = d.id
            ORDER BY d.created_at DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [self._row_to_document(row) for row in rows]

    async def get_document(self, document_id: UUID) -> DocumentRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT d.*, COALESCE(c.cnt, 0) AS chunk_count
                FROM public.documents d
                LEFT JOIN (
                    SELECT document_id, count(*) AS cnt
                    FROM public.document_chunks
                    GROUP BY document_id
                ) c ON c.document_id = d.id
                WHERE d.id = $1
                """,
                document_id,
            )
        return self._row_to_document(row) if row else None

    async def list_document_sections(
        self,
        document_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[DocumentSectionRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.document_sections
            WHERE document_id = $1
        """
        list_sql = """
            SELECT
                id, document_id, section_index, parent_section_id,
                section_number, section_title, section_kind, page_start, page_end,
                raw_text, created_at
            FROM public.document_sections
            WHERE document_id = $1
            ORDER BY section_index ASC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, document_id) or 0)
            rows = await conn.fetch(list_sql, document_id, page_size, offset)
        return total, [self._row_to_section_row(row) for row in rows]

    async def list_document_knowledge_chunks(
        self,
        document_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[DocumentKnowledgeChunkRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.knowledge_chunks
            WHERE document_id = $1
        """
        list_sql = """
            SELECT
                id, document_id, section_id, product_id,
                kind::text AS kind, chunk_index, section_type, subsection_type, topic,
                content, token_count, contains_table, contains_dose,
                species, metadata, created_at
            FROM public.knowledge_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, document_id) or 0)
            rows = await conn.fetch(list_sql, document_id, page_size, offset)
        return total, [self._row_to_knowledge_chunk_row(row) for row in rows]

    async def list_document_legacy_chunks(
        self,
        document_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[DocumentLegacyChunkRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.document_chunks
            WHERE document_id = $1
        """
        list_sql = """
            SELECT id, document_id, chunk_index, content, token_count, metadata, created_at
            FROM public.document_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, document_id) or 0)
            rows = await conn.fetch(list_sql, document_id, page_size, offset)
        return total, [self._row_to_legacy_chunk_row(row) for row in rows]

    async def list_document_faq_entries(
        self,
        document_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[DocumentFaqEntryRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.faq_entries
            WHERE document_id = $1
        """
        list_sql = """
            SELECT id, product_id, document_id, question, answer, source_page, created_at
            FROM public.faq_entries
            WHERE document_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, document_id) or 0)
            rows = await conn.fetch(list_sql, document_id, page_size, offset)
        return total, [self._row_to_faq_row(row) for row in rows]

    async def find_by_content_sha256(self, sha: str) -> DocumentRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id,
                       title,
                       product_name,
                       country_iso,
                       language,
                       status,
                       source_filename,
                       content_sha256,
                       classification,
                       uploaded_by,
                       validated_by,
                       validated_at,
                       created_at,
                       updated_at,
                       0 AS chunk_count
                FROM public.documents
                WHERE content_sha256 = $1
                """,
                sha,
            )
        return self._row_to_document(row) if row else None

    async def create_pending(
        self,
        *,
        title: str,
        product_name: str | None,
        country_iso: str | None,
        language: str,
        source_filename: str | None,
        content_sha256: str,
        uploaded_by: UUID | None,
        kind: str = "bitacora",
        product_id: UUID | None = None,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.documents
                    (title, product_name, country_iso, language, status,
                     source_filename, content_sha256, uploaded_by,
                     kind, product_id)
                VALUES ($1, $2, $3, $4, 'processing', $5, $6, $7,
                        $8::public.document_kind, $9)
                RETURNING id
                """,
                title,
                product_name,
                country_iso,
                language,
                source_filename,
                content_sha256,
                uploaded_by,
                kind,
                product_id,
            )
        return row["id"]

    async def mark_processing(self, document_id: UUID) -> None:
        """Marca un documento ya creado como `processing` para reingesta."""

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.documents
                SET status = 'processing',
                    classification = classification - 'error'
                WHERE id = $1
                """,
                document_id,
            )

    async def delete_sections(
        self, conn: asyncpg.Connection, document_id: UUID
    ) -> None:
        await conn.execute(
            "DELETE FROM public.document_sections WHERE document_id = $1",
            document_id,
        )

    async def insert_sections(
        self,
        conn: asyncpg.Connection,
        document_id: UUID,
        sections: Sequence[SectionInput],
    ) -> dict[int, UUID]:
        """Inserta secciones en orden y devuelve mapa section_index -> id.

        Crea primero todas las filas (parent_section_id=NULL) y en una
        segunda pasada actualiza los parents que correspondan, asi evitamos
        depender del orden de inserts cuando hay jerarquia.
        """

        if not sections:
            return {}

        ordered = sorted(sections, key=lambda s: s.section_index)
        index_to_id: dict[int, UUID] = {}
        for section in ordered:
            row = await conn.fetchrow(
                """
                INSERT INTO public.document_sections
                    (document_id, section_index, section_number,
                     section_title, section_kind, page_start, page_end,
                     raw_text)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                document_id,
                section.section_index,
                section.section_number,
                section.section_title,
                section.section_kind,
                section.page_start,
                section.page_end,
                section.raw_text,
            )
            index_to_id[section.section_index] = row["id"]

        for section in ordered:
            if section.parent_index is None:
                continue
            parent_id = index_to_id.get(section.parent_index)
            if parent_id is None:
                continue
            await conn.execute(
                """
                UPDATE public.document_sections
                SET parent_section_id = $2
                WHERE document_id = $1 AND section_index = $3
                """,
                document_id,
                parent_id,
                section.section_index,
            )

        return index_to_id

    async def mark_validated(
        self,
        document_id: UUID,
        *,
        markdown: str,
        validated_by: UUID,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.documents
                SET status = 'validated',
                    markdown = $2,
                    validated_by = $3,
                    validated_at = now()
                WHERE id = $1
                """,
                document_id,
                markdown,
                validated_by,
            )

    async def mark_failed(self, document_id: UUID, reason: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.documents SET status = 'failed', classification = "
                "classification || jsonb_build_object('error', $2::text) "
                "WHERE id = $1",
                document_id,
                reason,
            )

    async def update_document(
        self,
        document_id: UUID,
        *,
        fields: dict[str, Any],
    ) -> DocumentRow | None:
        if not fields:
            return await self.get_document(document_id)
        keys = list(fields.keys())
        values = list(fields.values())
        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(keys))
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"UPDATE public.documents SET {set_clause} WHERE id = $1",
                document_id,
                *values,
            )
        return await self.get_document(document_id)

    @staticmethod
    def _row_to_document(row: Any) -> DocumentRow:
        data = dict(row)
        classification = data.get("classification")
        if isinstance(classification, str):
            classification = json.loads(classification)
        return DocumentRow(
            id=data["id"],
            title=data["title"],
            product_name=data.get("product_name"),
            country_iso=data.get("country_iso"),
            language=data.get("language", "es"),
            status=data["status"],
            source_filename=data.get("source_filename"),
            content_sha256=data.get("content_sha256"),
            markdown=data.get("markdown"),
            classification=classification or {},
            uploaded_by=data.get("uploaded_by"),
            validated_by=data.get("validated_by"),
            validated_at=data.get("validated_at"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            kind=str(data.get("kind") or "bitacora"),
            product_id=data.get("product_id"),
            chunk_count=int(data.get("chunk_count") or 0),
        )

    @staticmethod
    def _parse_json(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return {}
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _row_to_section_row(row: Any) -> DocumentSectionRow:
        return DocumentSectionRow(
            id=row["id"],
            document_id=row["document_id"],
            section_index=row["section_index"],
            parent_section_id=row["parent_section_id"],
            section_number=row["section_number"],
            section_title=row["section_title"],
            section_kind=row["section_kind"],
            page_start=row["page_start"],
            page_end=row["page_end"],
            raw_text=row["raw_text"],
            created_at=row["created_at"],
        )

    @classmethod
    def _row_to_knowledge_chunk_row(cls, row: Any) -> DocumentKnowledgeChunkRow:
        return DocumentKnowledgeChunkRow(
            id=row["id"],
            document_id=row["document_id"],
            section_id=row["section_id"],
            product_id=row["product_id"],
            kind=row["kind"],
            chunk_index=row["chunk_index"],
            section_type=row["section_type"],
            subsection_type=row["subsection_type"],
            topic=row["topic"],
            content=row["content"],
            token_count=row["token_count"],
            contains_table=bool(row["contains_table"]),
            contains_dose=bool(row["contains_dose"]),
            species=list(row["species"] or []),
            metadata=cls._parse_json(row["metadata"]),
            created_at=row["created_at"],
        )

    @classmethod
    def _row_to_legacy_chunk_row(cls, row: Any) -> DocumentLegacyChunkRow:
        return DocumentLegacyChunkRow(
            id=row["id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            token_count=row["token_count"],
            metadata=cls._parse_json(row["metadata"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_faq_row(row: Any) -> DocumentFaqEntryRow:
        return DocumentFaqEntryRow(
            id=row["id"],
            product_id=row["product_id"],
            document_id=row["document_id"],
            question=row["question"],
            answer=row["answer"],
            source_page=row["source_page"],
            created_at=row["created_at"],
        )
