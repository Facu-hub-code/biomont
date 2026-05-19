"""Vinculos N:M entre productos y documentos (spec 006)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class LinkedDocumentRow:
    document_id: UUID
    title: str
    kind: str
    status: str
    country_iso: str | None
    is_primary: bool
    updated_at: datetime


@dataclass(slots=True)
class LinkedProductRow:
    product_id: UUID
    name: str
    brand: str
    is_primary: bool


class DocumentProductRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_documents_for_product(
        self,
        product_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[LinkedDocumentRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.document_products dp
            WHERE dp.product_id = $1
        """
        list_sql = """
            SELECT
                d.id AS document_id,
                d.title,
                d.kind::text AS kind,
                d.status::text AS status,
                d.country_iso,
                dp.is_primary,
                d.updated_at
            FROM public.document_products dp
            JOIN public.documents d ON d.id = dp.document_id
            WHERE dp.product_id = $1
            ORDER BY dp.is_primary DESC, d.updated_at DESC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, product_id) or 0)
            rows = await conn.fetch(list_sql, product_id, page_size, offset)
        return total, [self._row_linked_document(r) for r in rows]

    async def list_products_for_document(
        self, document_id: UUID
    ) -> list[LinkedProductRow]:
        sql = """
            SELECT
                p.id AS product_id,
                p.name,
                p.brand,
                dp.is_primary
            FROM public.document_products dp
            JOIN public.products p ON p.id = dp.product_id
            WHERE dp.document_id = $1
            ORDER BY dp.is_primary DESC, p.name ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, document_id)
        return [self._row_linked_product(r) for r in rows]

    async def link(
        self,
        *,
        product_id: UUID,
        document_id: UUID,
        is_primary: bool = False,
        created_by: UUID | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO public.document_products
                        (document_id, product_id, is_primary, created_by)
                    VALUES ($1, $2, $3, $4)
                    """,
                    document_id,
                    product_id,
                    is_primary,
                    created_by,
                )
                if is_primary:
                    await self._set_primary_on_conn(
                        conn, document_id=document_id, product_id=product_id
                    )
                else:
                    has_primary = await conn.fetchval(
                        """
                        SELECT 1 FROM public.document_products
                        WHERE document_id = $1 AND is_primary
                        LIMIT 1
                        """,
                        document_id,
                    )
                    if not has_primary:
                        await self._set_primary_on_conn(
                            conn,
                            document_id=document_id,
                            product_id=product_id,
                        )
                    else:
                        await self._sync_document_product_id_on_conn(
                            conn, document_id
                        )

    async def unlink(self, *, product_id: UUID, document_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    DELETE FROM public.document_products
                    WHERE product_id = $1 AND document_id = $2
                    RETURNING is_primary
                    """,
                    product_id,
                    document_id,
                )
                if row is None:
                    return False
                if row["is_primary"]:
                    await self._promote_next_primary_on_conn(conn, document_id)
                else:
                    await self._sync_document_product_id_on_conn(conn, document_id)
                return True

    async def replace_for_document(
        self,
        *,
        document_id: UUID,
        product_ids: list[UUID],
        primary_product_id: UUID | None,
        created_by: UUID | None = None,
    ) -> None:
        unique_ids = list(dict.fromkeys(product_ids))
        if primary_product_id is not None and primary_product_id not in unique_ids:
            raise ValueError("primary_product_id debe estar en product_ids")

        if not unique_ids:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "DELETE FROM public.document_products WHERE document_id = $1",
                        document_id,
                    )
                    await conn.execute(
                        "UPDATE public.documents SET product_id = NULL WHERE id = $1",
                        document_id,
                    )
            return

        primary = primary_product_id or unique_ids[0]

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM public.document_products WHERE document_id = $1",
                    document_id,
                )
                for pid in unique_ids:
                    await conn.execute(
                        """
                        INSERT INTO public.document_products
                            (document_id, product_id, is_primary, created_by)
                        VALUES ($1, $2, $3, $4)
                        """,
                        document_id,
                        pid,
                        pid == primary,
                        created_by,
                    )
                await self._sync_document_product_id_on_conn(conn, document_id)

    async def document_exists(self, document_id: UUID) -> bool:
        sql = "SELECT 1 FROM public.documents WHERE id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, document_id)
        return row is not None

    async def product_exists(self, product_id: UUID) -> bool:
        sql = "SELECT 1 FROM public.products WHERE id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, product_id)
        return row is not None

    async def link_exists(self, *, product_id: UUID, document_id: UUID) -> bool:
        sql = """
            SELECT 1 FROM public.document_products
            WHERE product_id = $1 AND document_id = $2
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, product_id, document_id)
        return row is not None

    async def _set_primary_on_conn(
        self,
        conn: asyncpg.Connection,
        *,
        document_id: UUID,
        product_id: UUID,
    ) -> None:
        await conn.execute(
            """
            UPDATE public.document_products
            SET is_primary = (product_id = $2)
            WHERE document_id = $1
            """,
            document_id,
            product_id,
        )
        await conn.execute(
            "UPDATE public.documents SET product_id = $2 WHERE id = $1",
            document_id,
            product_id,
        )

    async def _sync_document_product_id_on_conn(
        self, conn: asyncpg.Connection, document_id: UUID
    ) -> None:
        row = await conn.fetchrow(
            """
            SELECT product_id
            FROM public.document_products
            WHERE document_id = $1 AND is_primary
            LIMIT 1
            """,
            document_id,
        )
        primary = row["product_id"] if row else None
        await conn.execute(
            "UPDATE public.documents SET product_id = $2 WHERE id = $1",
            document_id,
            primary,
        )

    async def _promote_next_primary_on_conn(
        self, conn: asyncpg.Connection, document_id: UUID
    ) -> None:
        row = await conn.fetchrow(
            """
            SELECT product_id
            FROM public.document_products
            WHERE document_id = $1
            ORDER BY created_at ASC
            LIMIT 1
            """,
            document_id,
        )
        if row is None:
            await conn.execute(
                "UPDATE public.documents SET product_id = NULL WHERE id = $1",
                document_id,
            )
            return
        await self._set_primary_on_conn(
            conn, document_id=document_id, product_id=row["product_id"]
        )

    @staticmethod
    def _row_linked_document(row: asyncpg.Record) -> LinkedDocumentRow:
        return LinkedDocumentRow(
            document_id=row["document_id"],
            title=row["title"],
            kind=row["kind"],
            status=row["status"],
            country_iso=row["country_iso"],
            is_primary=bool(row["is_primary"]),
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_linked_product(row: asyncpg.Record) -> LinkedProductRow:
        return LinkedProductRow(
            product_id=row["product_id"],
            name=row["name"],
            brand=row["brand"],
            is_primary=bool(row["is_primary"]),
        )
