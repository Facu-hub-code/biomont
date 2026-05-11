"""Persistencia de `documents` (sin chunks; estos viven en RagRepository)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

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
    chunk_count: int = 0


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class DocumentRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_documents(self) -> list[DocumentRow]:
        query = """
            SELECT d.*,
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

    async def find_by_content_sha256(self, sha: str) -> DocumentRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT *, 0 AS chunk_count FROM public.documents WHERE content_sha256 = $1",
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
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.documents
                    (title, product_name, country_iso, language, status,
                     source_filename, content_sha256, uploaded_by)
                VALUES ($1, $2, $3, $4, 'processing', $5, $6, $7)
                RETURNING id
                """,
                title,
                product_name,
                country_iso,
                language,
                source_filename,
                content_sha256,
                uploaded_by,
            )
        return row["id"]

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
            chunk_count=int(data.get("chunk_count") or 0),
        )
