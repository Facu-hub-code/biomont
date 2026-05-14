"""FAQ del balotario (spec 003).

Retrieval directo con fusion trigram + embedding, separado del retrieval
general de `knowledge_chunks`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

import asyncpg
import numpy as np

from biomont_common.db.pool import DatabasePool
from biomont_common.db.product_repository import normalize_text
from biomont_common.schemas.knowledge import FaqHit


@dataclass(slots=True)
class FaqInput:
    product_id: UUID | None
    document_id: UUID
    question: str
    answer: str
    embedding: Sequence[float]
    source_page: int | None = None


class FaqRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def delete_for_document(
        self, conn: asyncpg.Connection, document_id: UUID
    ) -> None:
        await conn.execute(
            "DELETE FROM public.faq_entries WHERE document_id = $1",
            document_id,
        )

    async def insert_many(
        self,
        conn: asyncpg.Connection,
        entries: Sequence[FaqInput],
    ) -> int:
        if not entries:
            return 0
        await conn.executemany(
            """
            INSERT INTO public.faq_entries
                (product_id, document_id, question, answer, embedding,
                 source_page)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            [
                (
                    e.product_id,
                    e.document_id,
                    e.question,
                    e.answer,
                    np.asarray(e.embedding, dtype=np.float32),
                    e.source_page,
                )
                for e in entries
            ],
        )
        return len(entries)

    async def search(
        self,
        *,
        query_text: str,
        query_embedding: Sequence[float],
        product_id: UUID | None,
        vector_weight: float,
        bm25_weight: float,
        top_k: int = 3,
        candidate_k: int = 10,
    ) -> list[FaqHit]:
        """Devuelve top-k FAQ por fusion ponderada vector + BM25.

        Si `product_id` esta dado, restringe al producto correspondiente.
        FAQ con `product_id=NULL` no se incluyen para no contaminar la
        respuesta cuando se conoce el producto.
        """

        embedding_array = np.asarray(query_embedding, dtype=np.float32)
        normalized = normalize_text(query_text)
        if not normalized:
            return []

        sql = """
            WITH vec AS (
                SELECT f.id, 1 - (f.embedding <=> $1) AS vec_score
                FROM public.faq_entries f
                WHERE ($2::uuid IS NULL OR f.product_id = $2)
                ORDER BY f.embedding <=> $1
                LIMIT $3
            ),
            bm AS (
                SELECT f.id,
                       GREATEST(
                           ts_rank_cd(f.tsv, plainto_tsquery('spanish', $4)),
                           similarity(f.normalized_question, $5)
                       ) AS bm_score
                FROM public.faq_entries f
                WHERE ($2::uuid IS NULL OR f.product_id = $2)
                  AND (
                      f.tsv @@ plainto_tsquery('spanish', $4)
                      OR f.normalized_question %% $5
                  )
                ORDER BY bm_score DESC
                LIMIT $3
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
                       ) AS bm_n
                FROM agg
            )
            SELECT f.id, f.product_id, f.document_id, f.question, f.answer,
                   ($6::float * n.vec_n + $7::float * n.bm_n) AS final_score
            FROM norm n
            JOIN public.faq_entries f ON f.id = n.id
            ORDER BY final_score DESC
            LIMIT $8
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                sql,
                embedding_array,
                product_id,
                candidate_k,
                query_text,
                normalized,
                vector_weight,
                bm25_weight,
                top_k,
            )

        return [
            FaqHit(
                faq_id=r["id"],
                product_id=r["product_id"],
                document_id=r["document_id"],
                question=r["question"],
                answer=r["answer"],
                final_score=max(0.0, min(1.0, float(r["final_score"] or 0.0))),
            )
            for r in rows
        ]
