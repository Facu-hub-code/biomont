"""Consultas batch para enriquecer detalle de agent_decisions (spec 010)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class DocumentTitleRow:
    id: UUID
    title: str


@dataclass(slots=True)
class KnowledgeChunkRow:
    id: UUID
    document_id: UUID
    kind: str
    chunk_index: int
    section_type: str | None
    subsection_type: str | None
    topic: str | None
    content: str


@dataclass(slots=True)
class ProductNameRow:
    id: UUID
    name: str


class AgentDecisionEnrichmentRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def fetch_documents_by_ids(self, document_ids: list[UUID]) -> dict[UUID, DocumentTitleRow]:
        if not document_ids:
            return {}
        sql = """
            SELECT id, title
            FROM public.documents
            WHERE id = ANY($1::uuid[])
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, document_ids)
        return {
            row["id"]: DocumentTitleRow(id=row["id"], title=row["title"])
            for row in rows
        }

    async def fetch_knowledge_chunks_by_ids(
        self, chunk_ids: list[UUID]
    ) -> dict[UUID, KnowledgeChunkRow]:
        if not chunk_ids:
            return {}
        sql = """
            SELECT
                id,
                document_id,
                kind::text AS kind,
                chunk_index,
                section_type,
                subsection_type,
                topic,
                content
            FROM public.knowledge_chunks
            WHERE id = ANY($1::uuid[])
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, chunk_ids)
        return {
            row["id"]: KnowledgeChunkRow(
                id=row["id"],
                document_id=row["document_id"],
                kind=row["kind"],
                chunk_index=row["chunk_index"],
                section_type=row["section_type"],
                subsection_type=row["subsection_type"],
                topic=row["topic"],
                content=row["content"],
            )
            for row in rows
        }

    async def fetch_products_by_ids(self, product_ids: list[UUID]) -> dict[UUID, ProductNameRow]:
        if not product_ids:
            return {}
        sql = """
            SELECT id, name
            FROM public.products
            WHERE id = ANY($1::uuid[])
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, product_ids)
        return {row["id"]: ProductNameRow(id=row["id"], name=row["name"]) for row in rows}
