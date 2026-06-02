"""Administracion del comparador comercial (spec 012)."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool


def slugify_column(header: str) -> str:
    normalized = unicodedata.normalize("NFKD", header.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", "_", ascii_text)
    return cleaned.strip("_") or "column"


@dataclass(frozen=True, slots=True)
class ComparisonSetRow:
    id: UUID
    subject_product_id: UUID
    completeness_status: str
    published_version: int
    source_document_id: UUID | None


@dataclass(frozen=True, slots=True)
class CompetitorRow:
    id: UUID
    name: str
    brand: str | None
    is_internal: bool
    linked_product_id: UUID | None


class ComparisonAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_competitors(self, *, page: int, page_size: int) -> tuple[int, list[CompetitorRow]]:
        offset = (page - 1) * page_size
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM public.competitors")
            rows = await conn.fetch(
                """
                SELECT id, name, brand, is_internal, linked_product_id
                FROM public.competitors
                ORDER BY name
                LIMIT $1 OFFSET $2
                """,
                page_size,
                offset,
            )
        return int(total or 0), [_competitor_row(r) for r in rows]

    async def create_competitor(
        self,
        *,
        name: str,
        brand: str | None,
        is_internal: bool,
        linked_product_id: UUID | None,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.competitors (name, brand, is_internal, linked_product_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                name,
                brand,
                is_internal,
                linked_product_id,
            )
        return row["id"]

    async def get_or_create_set(self, subject_product_id: UUID) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.commercial_comparison_sets (subject_product_id)
                VALUES ($1)
                ON CONFLICT (subject_product_id) DO UPDATE
                    SET updated_at = now()
                RETURNING id
                """,
                subject_product_id,
            )
        return row["id"]

    async def get_set_by_product(self, product_id: UUID) -> ComparisonSetRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, subject_product_id, completeness_status,
                       published_version, source_document_id
                FROM public.commercial_comparison_sets
                WHERE subject_product_id = $1
                """,
                product_id,
            )
        if row is None:
            return None
        return ComparisonSetRow(
            id=row["id"],
            subject_product_id=row["subject_product_id"],
            completeness_status=row["completeness_status"],
            published_version=row["published_version"],
            source_document_id=row["source_document_id"],
        )

    async def clear_draft(self, set_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    DELETE FROM public.commercial_comparison_cells
                    WHERE published_version = 0
                      AND row_id IN (
                          SELECT id FROM public.commercial_comparison_rows
                          WHERE set_id = $1 AND published_version = 0
                      )
                    """,
                    set_id,
                )
                await conn.execute(
                    """
                    DELETE FROM public.commercial_comparison_rows
                    WHERE set_id = $1 AND published_version = 0
                    """,
                    set_id,
                )
                await conn.execute(
                    """
                    DELETE FROM public.commercial_comparison_columns
                    WHERE set_id = $1 AND published_version = 0
                    """,
                    set_id,
                )

    async def import_commercial_sheet(
        self,
        *,
        set_id: UUID,
        subject_product_id: UUID,
        subject_product_name: str,
        headers: list[str],
        rows: list[list[Any]],
        source_document_id: UUID | None,
    ) -> dict[str, Any]:
        column_keys = [slugify_column(h) for h in headers]
        imported_rows = 0
        gaps_created = 0

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self.clear_draft(set_id)

                for idx, header in enumerate(headers):
                    await conn.execute(
                        """
                        INSERT INTO public.commercial_comparison_columns (
                            set_id, column_key, header_label, sort_order, published_version
                        ) VALUES ($1, $2, $3, $4, 0)
                        ON CONFLICT (set_id, column_key, published_version) DO UPDATE
                            SET header_label = EXCLUDED.header_label,
                                sort_order = EXCLUDED.sort_order
                        """,
                        set_id,
                        column_keys[idx],
                        header,
                        idx,
                    )

                product_col_idx = next(
                    (i for i, k in enumerate(column_keys) if k in ("producto", "product")),
                    0,
                )

                for sort_order, row_values in enumerate(rows, start=1):
                    if not any(v is not None and str(v).strip() for v in row_values):
                        continue
                    display_name = str(row_values[product_col_idx] or "").strip()
                    if not display_name:
                        continue

                    is_subject = (
                        subject_product_name.lower() in display_name.lower()
                        or display_name.lower() in subject_product_name.lower()
                    )
                    competitor_id = None
                    linked_product_id = subject_product_id if is_subject else None

                    if not is_subject:
                        comp = await conn.fetchrow(
                            """
                            INSERT INTO public.competitors (name)
                            VALUES ($1)
                            ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
                            RETURNING id
                            """,
                            display_name.split("\n")[0][:200],
                        )
                        competitor_id = comp["id"]

                    row_record = await conn.fetchrow(
                        """
                        INSERT INTO public.commercial_comparison_rows (
                            set_id, display_name, competitor_id, linked_product_id,
                            is_subject, sort_order, published_version, source_row
                        ) VALUES ($1, $2, $3, $4, $5, $6, 0, $7::jsonb)
                        RETURNING id
                        """,
                        set_id,
                        display_name,
                        competitor_id,
                        linked_product_id if is_subject else None,
                        is_subject,
                        sort_order,
                        json.dumps({"row": sort_order}),
                    )
                    row_id = row_record["id"]
                    imported_rows += 1

                    for col_idx, col_key in enumerate(column_keys):
                        if col_idx >= len(row_values):
                            continue
                        val = row_values[col_idx]
                        text = str(val).strip() if val is not None else None
                        await conn.execute(
                            """
                            INSERT INTO public.commercial_comparison_cells (
                                row_id, column_key, value_text, published_version
                            ) VALUES ($1, $2, $3, 0)
                            """,
                            row_id,
                            col_key,
                            text,
                        )
                        if col_key in ("formula", "dosis", "especies", "especies_de_destino"):
                            if not text:
                                gaps_created += 1
                                await conn.execute(
                                    """
                                    INSERT INTO public.commercial_comparison_gaps (
                                        set_id, gap_type, severity, details
                                    ) VALUES ($1, 'missing_cell', 'blocking', $2::jsonb)
                                    """,
                                    set_id,
                                    json.dumps(
                                        {
                                            "column": col_key,
                                            "row": display_name,
                                        }
                                    ),
                                )

                await conn.execute(
                    """
                    UPDATE public.commercial_comparison_sets
                    SET source_document_id = COALESCE($2, source_document_id),
                        completeness_status = CASE
                            WHEN $3 > 0 THEN 'incomplete' ELSE 'incomplete'
                        END,
                        updated_at = now()
                    WHERE id = $1
                    """,
                    set_id,
                    source_document_id,
                    gaps_created,
                )

        return {
            "imported_rows": imported_rows,
            "gaps_created": gaps_created,
            "columns": len(headers),
        }

    async def publish_set(self, set_id: UUID, *, published_by: UUID | None) -> int:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                set_row = await conn.fetchrow(
                    """
                    SELECT id, published_version FROM public.commercial_comparison_sets
                    WHERE id = $1 FOR UPDATE
                    """,
                    set_id,
                )
                if set_row is None:
                    raise ValueError("set_not_found")

                new_version = set_row["published_version"] + 1

                await conn.execute(
                    """
                    INSERT INTO public.commercial_comparison_columns (
                        set_id, column_key, header_label, sort_order, published_version
                    )
                    SELECT set_id, column_key, header_label, sort_order, $2
                    FROM public.commercial_comparison_columns
                    WHERE set_id = $1 AND published_version = 0
                    """,
                    set_id,
                    new_version,
                )

                draft_rows = await conn.fetch(
                    """
                    SELECT id, display_name, competitor_id, linked_product_id,
                           is_subject, sort_order, source_row
                    FROM public.commercial_comparison_rows
                    WHERE set_id = $1 AND published_version = 0
                    """,
                    set_id,
                )
                if not draft_rows:
                    raise ValueError("no_draft_rows")

                id_map: dict[UUID, UUID] = {}
                for dr in draft_rows:
                    new_row = await conn.fetchrow(
                        """
                        INSERT INTO public.commercial_comparison_rows (
                            set_id, display_name, competitor_id, linked_product_id,
                            is_subject, sort_order, published_version, source_row
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id
                        """,
                        set_id,
                        dr["display_name"],
                        dr["competitor_id"],
                        dr["linked_product_id"],
                        dr["is_subject"],
                        dr["sort_order"],
                        new_version,
                        dr["source_row"],
                    )
                    id_map[dr["id"]] = new_row["id"]

                for old_id, new_id in id_map.items():
                    await conn.execute(
                        """
                        INSERT INTO public.commercial_comparison_cells (
                            row_id, column_key, value_text, published_version
                        )
                        SELECT $2, column_key, value_text, $3
                        FROM public.commercial_comparison_cells
                        WHERE row_id = $1 AND published_version = 0
                        """,
                        old_id,
                        new_id,
                        new_version,
                    )

                snapshot = {"set_id": str(set_id), "version": new_version}
                await conn.execute(
                    """
                    INSERT INTO public.commercial_comparison_versions (
                        set_id, version, snapshot, published_by
                    ) VALUES ($1, $2, $3::jsonb, $4)
                    """,
                    set_id,
                    new_version,
                    json.dumps(snapshot),
                    published_by,
                )
                await conn.execute(
                    """
                    UPDATE public.commercial_comparison_sets
                    SET published_version = $2,
                        completeness_status = 'complete',
                        updated_at = now(),
                        updated_by = $3
                    WHERE id = $1
                    """,
                    set_id,
                    new_version,
                    published_by,
                )
                await conn.execute(
                    """
                    UPDATE public.commercial_comparison_gaps
                    SET resolved_at = now()
                    WHERE set_id = $1 AND resolved_at IS NULL
                    """,
                    set_id,
                )
        return new_version


def _competitor_row(row: asyncpg.Record) -> CompetitorRow:
    return CompetitorRow(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        is_internal=row["is_internal"],
        linked_product_id=row["linked_product_id"],
    )
