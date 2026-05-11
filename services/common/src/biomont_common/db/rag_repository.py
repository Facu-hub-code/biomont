"""Repositorio para el flujo de RAG sobre `documents` y `document_chunks`.

Concentra el SQL en un unico modulo (cumple
`.cursor/rules/dependency-constraints.mdc`: no SQL disperso en handlers o
herramientas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence
from uuid import UUID

import asyncpg
import numpy as np

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class ChunkHit:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    country_iso: str | None
    chunk_index: int
    content: str
    similarity: float
    metadata: dict


class RagRepository:
    """Encapsula consultas vectoriales y persistencia de chunks."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def search_similar_chunks(
        self,
        query_embedding: Sequence[float],
        allowed_countries: Iterable[str],
        top_k: int = 6,
    ) -> list[ChunkHit]:
        """Top-k chunks por similitud coseno con filtro de pais.

        - `allowed_countries` son los iso2 habilitados para el RTC.
        - Documentos `country_iso IS NULL` se consideran globales y
          siempre se incluyen.
        - Solo se consideran documentos en estado `validated`.
        """

        countries = list({c.upper() for c in allowed_countries if c})
        embedding_array = np.asarray(query_embedding, dtype=np.float32)

        query = """
            SELECT
                c.id              AS chunk_id,
                c.document_id     AS document_id,
                d.title           AS document_title,
                d.country_iso     AS country_iso,
                c.chunk_index     AS chunk_index,
                c.content         AS content,
                c.metadata        AS metadata,
                1 - (c.embedding <=> $1) AS similarity
            FROM public.document_chunks c
            JOIN public.documents d ON d.id = c.document_id
            WHERE d.status = 'validated'
              AND (d.country_iso IS NULL OR d.country_iso = ANY($2::char(2)[]))
            ORDER BY c.embedding <=> $1
            LIMIT $3
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, embedding_array, countries, top_k)

        return [
            ChunkHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                country_iso=row["country_iso"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                similarity=float(row["similarity"]),
                metadata=dict(row["metadata"] or {}),
            )
            for row in rows
        ]

    async def insert_chunks(
        self,
        conn: asyncpg.Connection,
        document_id: UUID,
        chunks: Sequence["ChunkInput"],
    ) -> None:
        """Inserta chunks ya embebidos en una transaccion provista."""

        await conn.executemany(
            """
            INSERT INTO public.document_chunks
                (document_id, chunk_index, content, token_count, metadata, embedding)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            [
                (
                    document_id,
                    chunk.index,
                    chunk.content,
                    chunk.token_count,
                    chunk.metadata_json,
                    np.asarray(chunk.embedding, dtype=np.float32),
                )
                for chunk in chunks
            ],
        )

    async def delete_chunks_for_document(
        self,
        conn: asyncpg.Connection,
        document_id: UUID,
    ) -> None:
        await conn.execute(
            "DELETE FROM public.document_chunks WHERE document_id = $1",
            document_id,
        )


@dataclass(slots=True)
class ChunkInput:
    index: int
    content: str
    token_count: int
    metadata_json: str
    embedding: Sequence[float]
