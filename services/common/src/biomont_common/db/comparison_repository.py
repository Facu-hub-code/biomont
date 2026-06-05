"""Repositorio del comparador comercial (spec 012)."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool
from biomont_common.schemas.comparison import (
    ComparisonColumn,
    ComparisonDiffItem,
    ComparisonDiffResult,
    ComparisonRow,
    ComparisonSimilarityItem,
    Competitor,
)


class ComparisonRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def find_competitor_by_query(self, query: str, limit: int = 5) -> list[Competitor]:
        normalized = query.strip().lower()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, brand, is_internal, linked_product_id,
                       similarity(normalized_name, public.immutable_unaccent_lower($1)) AS sim
                FROM public.competitors
                WHERE normalized_name % public.immutable_unaccent_lower($1)
                   OR name ILIKE '%' || $1 || '%'
                ORDER BY sim DESC NULLS LAST, name
                LIMIT $2
                """,
                normalized,
                limit,
            )
        return [_row_to_competitor(r) for r in rows]

    async def get_published_set(self, subject_product_id: UUID) -> asyncpg.Record | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT id, subject_product_id, completeness_status, published_version
                FROM public.commercial_comparison_sets
                WHERE subject_product_id = $1 AND published_version > 0
                """,
                subject_product_id,
            )

    async def get_columns(self, set_id: UUID, version: int) -> list[ComparisonColumn]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT column_key, header_label, sort_order
                FROM public.commercial_comparison_columns
                WHERE set_id = $1 AND published_version = $2
                ORDER BY sort_order, header_label
                """,
                set_id,
                version,
            )
        return [
            ComparisonColumn(
                column_key=r["column_key"],
                header_label=r["header_label"],
                sort_order=r["sort_order"],
            )
            for r in rows
        ]

    async def get_row_by_subject(self, set_id: UUID, version: int) -> ComparisonRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, display_name, is_subject, competitor_id, linked_product_id
                FROM public.commercial_comparison_rows
                WHERE set_id = $1 AND published_version = $2 AND is_subject = true
                LIMIT 1
                """,
                set_id,
                version,
            )
            if row is None:
                return None
            cells = await self._cells_for_row(conn=conn, row_id=row["id"], version=version)
        return ComparisonRow(
            id=row["id"],
            display_name=row["display_name"],
            is_subject=row["is_subject"],
            competitor_id=row["competitor_id"],
            linked_product_id=row["linked_product_id"],
            cells=cells,
        )

    async def get_row_by_competitor(
        self,
        set_id: UUID,
        version: int,
        *,
        competitor_id: UUID | None = None,
        linked_product_id: UUID | None = None,
        display_name: str | None = None,
    ) -> ComparisonRow | None:
        async with self._pool.acquire() as conn:
            if competitor_id is not None:
                row = await conn.fetchrow(
                    """
                    SELECT id, display_name, is_subject, competitor_id, linked_product_id
                    FROM public.commercial_comparison_rows
                    WHERE set_id = $1 AND published_version = $2
                      AND competitor_id = $3 AND is_subject = false
                    LIMIT 1
                    """,
                    set_id,
                    version,
                    competitor_id,
                )
            elif linked_product_id is not None:
                row = await conn.fetchrow(
                    """
                    SELECT id, display_name, is_subject, competitor_id, linked_product_id
                    FROM public.commercial_comparison_rows
                    WHERE set_id = $1 AND published_version = $2
                      AND linked_product_id = $3 AND is_subject = false
                    LIMIT 1
                    """,
                    set_id,
                    version,
                    linked_product_id,
                )
            elif display_name:
                row = await conn.fetchrow(
                    """
                    SELECT id, display_name, is_subject, competitor_id, linked_product_id
                    FROM public.commercial_comparison_rows
                    WHERE set_id = $1 AND published_version = $2
                      AND public.immutable_unaccent_lower(display_name)
                          = public.immutable_unaccent_lower($3)
                    LIMIT 1
                    """,
                    set_id,
                    version,
                    display_name,
                )
            else:
                return None
        if row is None:
            return None
        cells = await self._cells_for_row(row_id=row["id"], version=version)
        return ComparisonRow(
            id=row["id"],
            display_name=row["display_name"],
            is_subject=row["is_subject"],
            competitor_id=row["competitor_id"],
            linked_product_id=row["linked_product_id"],
            cells=cells,
        )

    async def _cells_for_row(
        self,
        *,
        conn=None,
        row_id: UUID,
        version: int,
    ) -> dict[str, str | None]:
        query = """
            SELECT column_key, value_text
            FROM public.commercial_comparison_cells
            WHERE row_id = $1 AND published_version = $2
        """
        if conn is not None:
            rows = await conn.fetch(query, row_id, version)
        else:
            async with self._pool.acquire() as acquired:
                rows = await acquired.fetch(query, row_id, version)
        return {r["column_key"]: r["value_text"] for r in rows}

    async def diff_rows(
        self,
        *,
        subject_product_id: UUID,
        subject_product_name: str,
        competitor_name: str,
        competitor_id: UUID | None = None,
        linked_product_id: UUID | None = None,
    ) -> ComparisonDiffResult | None:
        set_row = await self.get_published_set(subject_product_id)
        if set_row is None:
            return None
        if set_row["completeness_status"] != "complete":
            return None

        version = set_row["published_version"]
        set_id = set_row["id"]
        columns = await self.get_columns(set_id, version)
        subject_row = await self.get_row_by_subject(set_id, version)
        if subject_row is None:
            return None

        competitor_row = await self.get_row_by_competitor(
            set_id,
            version,
            competitor_id=competitor_id,
            linked_product_id=linked_product_id,
            display_name=competitor_name,
        )
        if competitor_row is None:
            return None

        differences: list[ComparisonDiffItem] = []
        similarities: list[ComparisonSimilarityItem] = []
        for col in columns:
            subj_val = (subject_row.cells.get(col.column_key) or "").strip()
            comp_val = (competitor_row.cells.get(col.column_key) or "").strip()
            if not subj_val and not comp_val:
                continue
            if subj_val == comp_val:
                similarities.append(
                    ComparisonSimilarityItem(
                        column_key=col.column_key,
                        header_label=col.header_label,
                        shared_value=subj_val,
                        sort_order=col.sort_order,
                    )
                )
                continue
            differences.append(
                ComparisonDiffItem(
                    column_key=col.column_key,
                    header_label=col.header_label,
                    subject_value=subj_val or "(sin dato)",
                    competitor_value=comp_val or "(sin dato)",
                    sort_order=col.sort_order,
                )
            )

        return ComparisonDiffResult(
            subject_product_id=subject_product_id,
            subject_name=subject_row.display_name,
            competitor_name=competitor_row.display_name,
            published_version=version,
            differences=differences,
            similarities=similarities,
        )


def _row_to_competitor(row: asyncpg.Record) -> Competitor:
    return Competitor(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        is_internal=row["is_internal"],
        linked_product_id=row["linked_product_id"],
    )


def format_comparison_diff(result: ComparisonDiffResult) -> str:
    """Plantilla neutra sin juicio de valor."""

    lines = [
        f"Comparando **{result.subject_name}** con **{result.competitor_name}** "
        f"(datos validados v{result.published_version}):",
        "",
    ]
    if not result.differences:
        lines.append(
            "No se encontraron diferencias en los campos comparables del cuadro comercial."
        )
    else:
        for item in result.differences:
            lines.append(f"- **{item.header_label}**:")
            lines.append(f"  - {result.subject_name}: {item.subject_value}")
            lines.append(f"  - {result.competitor_name}: {item.competitor_value}")
    lines.append("")
    lines.append("Fuente: comparativa comercial Biomont.")
    return "\n".join(lines)
