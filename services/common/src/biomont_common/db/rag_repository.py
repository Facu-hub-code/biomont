"""Repositorio para el flujo de RAG sobre `documents`, `document_chunks` y
`knowledge_chunks`.

Concentra el SQL en un unico modulo (cumple
`.cursor/rules/dependency-constraints.mdc`: no SQL disperso en handlers o
herramientas).

A partir de la spec 003 convive el camino "legacy" (`document_chunks`,
solo coseno) con el camino "graph" (`knowledge_chunks`, hibrido vec+BM25
con filtros pre-retrieval). El switch lo decide `AGENT_USE_GRAPH`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence
from uuid import UUID

import asyncpg
import numpy as np

from biomont_common.db.pool import DatabasePool
from biomont_common.db.product_repository import normalize_text
from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit


def _metadata_row_to_dict(value: Any) -> dict:
    """Normaliza `document_chunks.metadata` traído por asyncpg.

    Según tipo de columna/driver, puede llegar como ``dict`` o como ``str``
    JSON; ``dict("...")`` provoca ``ValueError``.
    """

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
    if isinstance(value, (bytes, bytearray)):
        return _metadata_row_to_dict(value.decode())
    return {}


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
                metadata=_metadata_row_to_dict(row["metadata"]),
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

    # ------------------------------------------------------------------
    # knowledge_chunks (spec 003): retrieval hibrido y persistencia.
    # ------------------------------------------------------------------

    async def delete_knowledge_chunks_for_document(
        self,
        conn: asyncpg.Connection,
        document_id: UUID,
    ) -> None:
        await conn.execute(
            "DELETE FROM public.knowledge_chunks WHERE document_id = $1",
            document_id,
        )

    async def insert_knowledge_chunks(
        self,
        conn: asyncpg.Connection,
        document_id: UUID,
        chunks: Sequence["KnowledgeChunkInput"],
    ) -> None:
        if not chunks:
            return
        await conn.executemany(
            """
            INSERT INTO public.knowledge_chunks
                (document_id, section_id, product_id, kind, chunk_index,
                 section_type, subsection_type, topic, content, token_count,
                 contains_table, contains_dose, species, metadata, embedding)
            VALUES
                ($1, $2, $3, $4::public.document_kind, $5,
                 $6, $7, $8, $9, $10,
                 $11, $12, $13::text[], $14::jsonb, $15)
            """,
            [
                (
                    document_id,
                    c.section_id,
                    c.product_id,
                    c.kind.value,
                    c.index,
                    c.section_type,
                    c.subsection_type,
                    c.topic,
                    c.content,
                    c.token_count,
                    c.contains_table,
                    c.contains_dose,
                    list(c.species),
                    c.metadata_json,
                    np.asarray(c.embedding, dtype=np.float32),
                )
                for c in chunks
            ],
        )

    async def search_hybrid_chunks(
        self,
        *,
        query_text: str,
        query_embedding: Sequence[float],
        allowed_countries: Iterable[str],
        product_id: UUID | None = None,
        kinds: Sequence[DocumentKind] | None = None,
        vector_weight: float,
        bm25_weight: float,
        top_k: int = 6,
        candidate_k: int = 25,
    ) -> list[HybridChunkHit]:
        """Top-k chunks por fusion ponderada vector + BM25 con filtros.

        Filtros pre-retrieval aplicados en cada CTE para evitar full scan:
        - `product_id`: si dado, restringe; si NULL acepta cualquier
          producto (incluye chunks sin producto).
        - `kinds`: si dado, restringe a esos tipos de documento.
        - `allowed_countries`: paises permitidos del RTC; documentos
          `country_iso=NULL` se consideran globales.
        - Solo `documents.status='validated'`.

        Normalizacion min-max acotada al universo candidato (CTE),
        no a toda la tabla.
        """

        countries = list({c.upper() for c in allowed_countries if c}) or None
        kinds_arr = [k.value for k in kinds] if kinds else None
        embedding_array = np.asarray(query_embedding, dtype=np.float32)
        normalized_query = normalize_text(query_text)

        sql = """
            WITH base AS (
                SELECT c.id, c.embedding, c.tsv, c.content, c.metadata,
                       c.product_id, c.kind, c.chunk_index, c.section_type,
                       c.document_id, d.title AS document_title,
                       d.country_iso
                FROM public.knowledge_chunks c
                JOIN public.documents d ON d.id = c.document_id
                WHERE d.status = 'validated'
                  AND (
                      $3::char(2)[] IS NULL
                      OR d.country_iso IS NULL
                      OR d.country_iso = ANY($3::char(2)[])
                  )
                  AND ($4::uuid IS NULL OR c.product_id = $4)
                  AND (
                      $5::text[] IS NULL
                      OR c.kind::text = ANY($5::text[])
                  )
            ),
            vec AS (
                SELECT id, 1 - (embedding <=> $1) AS vec_score
                FROM base
                ORDER BY embedding <=> $1
                LIMIT $6
            ),
            bm AS (
                SELECT id,
                       ts_rank_cd(tsv, plainto_tsquery('spanish', $2)) AS bm_score
                FROM base
                WHERE tsv @@ plainto_tsquery('spanish', $2)
                ORDER BY bm_score DESC
                LIMIT $6
            ),
            agg AS (
                SELECT id, MAX(vec_score) AS vec_score, MAX(bm_score) AS bm_score
                FROM (
                    SELECT id, vec_score, NULL::real AS bm_score FROM vec
                    UNION ALL
                    SELECT id, NULL::real, bm_score FROM bm
                ) u
                GROUP BY id
            ),
            norm AS (
                SELECT id,
                       COALESCE(
                           (vec_score - MIN(vec_score) OVER ()) /
                           NULLIF(MAX(vec_score) OVER () - MIN(vec_score) OVER (), 0),
                           CASE WHEN vec_score IS NOT NULL THEN 1.0 ELSE 0 END
                       ) AS vec_n,
                       COALESCE(
                           (bm_score - MIN(bm_score) OVER ()) /
                           NULLIF(MAX(bm_score) OVER () - MIN(bm_score) OVER (), 0),
                           CASE WHEN bm_score IS NOT NULL THEN 1.0 ELSE 0 END
                       ) AS bm_n,
                       vec_score,
                       bm_score
                FROM agg
            )
            SELECT b.id AS chunk_id, b.document_id, b.document_title,
                   b.product_id, b.kind, b.chunk_index, b.section_type,
                   b.content, b.country_iso, b.metadata,
                   n.vec_score, n.bm_score,
                   ($7::float * n.vec_n + $8::float * n.bm_n) AS final_score
            FROM norm n
            JOIN base b ON b.id = n.id
            ORDER BY final_score DESC
            LIMIT $9
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                sql,
                embedding_array,
                normalized_query or query_text,
                countries,
                product_id,
                kinds_arr,
                candidate_k,
                vector_weight,
                bm25_weight,
                top_k,
            )

        return [
            HybridChunkHit(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                document_title=r["document_title"],
                product_id=r["product_id"],
                kind=DocumentKind(r["kind"]),
                chunk_index=r["chunk_index"],
                section_type=r["section_type"],
                content=r["content"],
                country_iso=r["country_iso"],
                vector_score=(
                    float(r["vec_score"]) if r["vec_score"] is not None else None
                ),
                bm25_score=(
                    float(r["bm_score"]) if r["bm_score"] is not None else None
                ),
                final_score=max(0.0, min(1.0, float(r["final_score"] or 0.0))),
                metadata=_metadata_row_to_dict(r["metadata"]),
            )
            for r in rows
        ]


@dataclass(slots=True)
class ChunkInput:
    index: int
    content: str
    token_count: int
    metadata_json: str
    embedding: Sequence[float]


@dataclass(slots=True)
class KnowledgeChunkInput:
    """Chunk para `knowledge_chunks` (spec 003).

    `section_id` se referencia al `document_sections` correspondiente.
    `species` es array postgres; `metadata` jsonb opcional.
    """

    index: int
    content: str
    token_count: int
    embedding: Sequence[float]
    kind: DocumentKind
    section_id: UUID | None = None
    product_id: UUID | None = None
    section_type: str | None = None
    subsection_type: str | None = None
    topic: str | None = None
    contains_table: bool = False
    contains_dose: bool = False
    species: Sequence[str] = ()
    metadata_json: str = "{}"
