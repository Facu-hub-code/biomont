"""CRUD administrativo de products y product_aliases para backoffice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class ProductListRow:
    id: UUID
    name: str
    brand: str
    duration_type: str | None
    description: str | None
    country_iso: str | None
    created_at: datetime
    updated_at: datetime
    alias_count: int
    document_count: int


@dataclass(slots=True)
class ProductAliasRow:
    id: UUID
    product_id: UUID
    alias: str
    normalized_alias: str
    source: str
    confidence: float
    created_at: datetime


class ProductAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_products(
        self,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[ProductListRow]]:
        offset = (page - 1) * page_size
        count_sql = "SELECT count(*) FROM public.products"
        list_sql = """
            SELECT
                p.id,
                p.name,
                p.brand,
                p.duration_type,
                p.description,
                p.country_iso,
                p.created_at,
                p.updated_at,
                COALESCE(a.alias_count, 0) AS alias_count,
                COALESCE(d.document_count, 0) AS document_count
            FROM public.products p
            LEFT JOIN (
                SELECT product_id, count(*) AS alias_count
                FROM public.product_aliases
                GROUP BY product_id
            ) a ON a.product_id = p.id
            LEFT JOIN (
                SELECT product_id, count(*) AS document_count
                FROM public.document_products
                GROUP BY product_id
            ) d ON d.product_id = p.id
            ORDER BY p.name ASC
            LIMIT $1 OFFSET $2
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql) or 0)
            rows = await conn.fetch(list_sql, page_size, offset)
        return total, [self._row_to_product_list_item(row) for row in rows]

    async def get_product(self, product_id: UUID) -> ProductListRow | None:
        sql = """
            SELECT
                p.id,
                p.name,
                p.brand,
                p.duration_type,
                p.description,
                p.country_iso,
                p.created_at,
                p.updated_at,
                COALESCE(a.alias_count, 0) AS alias_count,
                COALESCE(d.document_count, 0) AS document_count
            FROM public.products p
            LEFT JOIN (
                SELECT product_id, count(*) AS alias_count
                FROM public.product_aliases
                GROUP BY product_id
            ) a ON a.product_id = p.id
            LEFT JOIN (
                SELECT product_id, count(*) AS document_count
                FROM public.document_products
                GROUP BY product_id
            ) d ON d.product_id = p.id
            WHERE p.id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, product_id)
        return self._row_to_product_list_item(row) if row else None

    async def create_product(
        self,
        *,
        name: str,
        brand: str,
        duration_type: str | None,
        description: str | None,
        country_iso: str | None,
    ) -> UUID:
        insert_product_sql = """
            INSERT INTO public.products
                (name, brand, duration_type, description, country_iso)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        insert_alias_sql = """
            INSERT INTO public.product_aliases
                (product_id, alias, source, confidence)
            VALUES ($1, $2, 'name', 1.0)
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    insert_product_sql,
                    name,
                    brand,
                    duration_type,
                    description,
                    country_iso,
                )
                product_id = row["id"]
                await conn.execute(insert_alias_sql, product_id, name.strip())
        return product_id

    async def update_product(
        self,
        product_id: UUID,
        *,
        name: str | None = None,
        brand: str | None = None,
        duration_type: str | None = None,
        description: str | None = None,
        country_iso: str | None = None,
    ) -> ProductListRow | None:
        sql = """
            UPDATE public.products
            SET
                name = COALESCE($2, name),
                brand = COALESCE($3, brand),
                duration_type = COALESCE($4, duration_type),
                description = COALESCE($5, description),
                country_iso = COALESCE($6, country_iso)
            WHERE id = $1
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                product_id,
                name,
                brand,
                duration_type,
                description,
                country_iso,
            )
        if row is None:
            return None
        return await self.get_product(product_id)

    async def delete_product(self, product_id: UUID) -> bool:
        sql = "DELETE FROM public.products WHERE id = $1"
        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, product_id)
        return result.endswith("1")

    async def list_aliases(
        self,
        product_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[ProductAliasRow]]:
        offset = (page - 1) * page_size
        count_sql = """
            SELECT count(*)
            FROM public.product_aliases
            WHERE product_id = $1
        """
        list_sql = """
            SELECT
                id, product_id, alias, normalized_alias, source, confidence, created_at
            FROM public.product_aliases
            WHERE product_id = $1
            ORDER BY alias ASC
            LIMIT $2 OFFSET $3
        """
        async with self._pool.acquire() as conn:
            total = int(await conn.fetchval(count_sql, product_id) or 0)
            rows = await conn.fetch(list_sql, product_id, page_size, offset)
        return total, [self._row_to_alias_item(row) for row in rows]

    async def get_alias(
        self,
        product_id: UUID,
        alias_id: UUID,
    ) -> ProductAliasRow | None:
        sql = """
            SELECT id, product_id, alias, normalized_alias, source, confidence, created_at
            FROM public.product_aliases
            WHERE id = $1 AND product_id = $2
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, alias_id, product_id)
        return self._row_to_alias_item(row) if row else None

    async def create_alias(
        self,
        *,
        product_id: UUID,
        alias: str,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> UUID:
        sql = """
            INSERT INTO public.product_aliases
                (product_id, alias, source, confidence)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, product_id, alias, source, confidence)
        return row["id"]

    async def update_alias(
        self,
        *,
        product_id: UUID,
        alias_id: UUID,
        alias: str | None = None,
        source: str | None = None,
        confidence: float | None = None,
    ) -> ProductAliasRow | None:
        sql = """
            UPDATE public.product_aliases
            SET
                alias = COALESCE($3, alias),
                source = COALESCE($4, source),
                confidence = COALESCE($5, confidence)
            WHERE id = $1 AND product_id = $2
            RETURNING id
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql, alias_id, product_id, alias, source, confidence
            )
        if row is None:
            return None
        return await self.get_alias(product_id, alias_id)

    async def delete_alias(self, *, product_id: UUID, alias_id: UUID) -> bool:
        sql = "DELETE FROM public.product_aliases WHERE id = $1 AND product_id = $2"
        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, alias_id, product_id)
        return result.endswith("1")

    @staticmethod
    def _row_to_product_list_item(row) -> ProductListRow:
        return ProductListRow(
            id=row["id"],
            name=row["name"],
            brand=row["brand"],
            duration_type=row["duration_type"],
            description=row["description"],
            country_iso=row["country_iso"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            alias_count=int(row["alias_count"] or 0),
            document_count=int(row["document_count"] or 0),
        )

    @staticmethod
    def _row_to_alias_item(row) -> ProductAliasRow:
        return ProductAliasRow(
            id=row["id"],
            product_id=row["product_id"],
            alias=row["alias"],
            normalized_alias=row["normalized_alias"],
            source=row["source"],
            confidence=float(row["confidence"]),
            created_at=row["created_at"],
        )
