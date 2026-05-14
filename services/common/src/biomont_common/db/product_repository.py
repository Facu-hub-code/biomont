"""Productos y aliases (spec 003).

Encapsula el SQL para resolucion deterministica de producto
(pg_trgm + matching exacto sobre `product_aliases`) y para mantenimiento
de la tabla `products`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence
from uuid import UUID

import asyncpg

from biomont_common.db.pool import DatabasePool
from biomont_common.schemas.products import (
    Product,
    ProductAlias,
    ProductCandidate,
)

_WS_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Normaliza al mismo dominio que `immutable_unaccent_lower` SQL.

    Combina NFKD + filtrado de combining + lowercase + colapso de espacios.
    Tests dependen de esta funcion, no del lado SQL.
    """

    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WS_RE.sub(" ", stripped.lower()).strip()


class ProductRepository:
    """Encapsula consultas sobre `products` y `product_aliases`."""

    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get_by_id(self, product_id: UUID) -> Product | None:
        query = """
            SELECT id, name, brand, duration_type, description, country_iso,
                   created_at, updated_at
            FROM public.products
            WHERE id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, product_id)
        return _row_to_product(row) if row else None

    async def list_all(self, country_iso: str | None = None) -> list[Product]:
        query = """
            SELECT id, name, brand, duration_type, description, country_iso,
                   created_at, updated_at
            FROM public.products
            WHERE ($1::char(2) IS NULL OR country_iso IS NULL OR country_iso = $1)
            ORDER BY name
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, country_iso)
        return [_row_to_product(r) for r in rows]

    async def find_or_create(
        self,
        *,
        name: str,
        country_iso: str | None = None,
        brand: str = "Biomont",
        duration_type: str | None = None,
        description: str | None = None,
    ) -> Product:
        """Idempotente: usa UNIQUE (lower(name), COALESCE(country_iso, 'XX'))."""

        query = """
            INSERT INTO public.products
                (name, brand, duration_type, description, country_iso)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (lower(name), COALESCE(country_iso, 'XX'::char(2)))
            DO UPDATE SET name = EXCLUDED.name
            RETURNING id, name, brand, duration_type, description, country_iso,
                      created_at, updated_at
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query, name, brand, duration_type, description, country_iso
            )
        assert row is not None
        return _row_to_product(row)

    async def add_aliases(
        self,
        product_id: UUID,
        aliases: Iterable[str],
        *,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> int:
        """Inserta aliases ignorando duplicados (`ON CONFLICT DO NOTHING`).

        Devuelve la cantidad de filas efectivamente insertadas.
        """

        unique_inputs = []
        seen: set[str] = set()
        for alias in aliases:
            cleaned = alias.strip()
            if not cleaned:
                continue
            key = normalize_text(cleaned)
            if key in seen:
                continue
            seen.add(key)
            unique_inputs.append(cleaned)

        if not unique_inputs:
            return 0

        query = """
            INSERT INTO public.product_aliases
                (product_id, alias, source, confidence)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (product_id, normalized_alias) DO NOTHING
        """
        inserted = 0
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for alias in unique_inputs:
                    result = await conn.execute(
                        query, product_id, alias, source, confidence
                    )
                    if result.endswith("0"):
                        continue
                    inserted += 1
        return inserted

    async def list_aliases(self, product_id: UUID) -> list[ProductAlias]:
        query = """
            SELECT id, product_id, alias, normalized_alias, source, confidence
            FROM public.product_aliases
            WHERE product_id = $1
            ORDER BY alias
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, product_id)
        return [
            ProductAlias(
                id=r["id"],
                product_id=r["product_id"],
                alias=r["alias"],
                normalized_alias=r["normalized_alias"],
                source=r["source"],
                confidence=float(r["confidence"]),
            )
            for r in rows
        ]

    async def search_candidates(
        self,
        query_text: str,
        *,
        allowed_countries: Sequence[str] | None = None,
        limit: int = 5,
    ) -> list[ProductCandidate]:
        """Resuelve candidatos por (1) exacto sobre normalized_alias, (2) trigram.

        El query SQL combina ambas estrategias en un solo statement:
        - Match exacto recibe similarity=1.0.
        - El resto se ordena por `similarity()` (pg_trgm) decreciente.

        `allowed_countries`: ISO2 de paises del RTC. Productos con
        `country_iso=NULL` se consideran globales y siempre matchean.
        """

        normalized = normalize_text(query_text)
        if not normalized:
            return []

        countries = (
            list({c.upper() for c in allowed_countries if c})
            if allowed_countries
            else None
        )

        sql = """
            WITH ranked AS (
                SELECT
                    p.id   AS product_id,
                    p.name AS product_name,
                    a.alias AS alias_matched,
                    CASE
                        WHEN a.normalized_alias = $1 THEN 1.0
                        ELSE similarity(a.normalized_alias, $1)
                    END AS sim,
                    p.country_iso
                FROM public.products p
                JOIN public.product_aliases a ON a.product_id = p.id
                WHERE
                    (
                        a.normalized_alias = $1
                        OR a.normalized_alias % $1
                    )
                    AND (
                        $2::char(2)[] IS NULL
                        OR p.country_iso IS NULL
                        OR p.country_iso = ANY($2::char(2)[])
                    )
            ),
            best AS (
                SELECT DISTINCT ON (product_id)
                    product_id, product_name, alias_matched, sim, country_iso
                FROM ranked
                ORDER BY product_id, sim DESC
            )
            SELECT product_id, product_name, alias_matched, sim
            FROM best
            ORDER BY sim DESC
            LIMIT $3
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, normalized, countries, limit)

        return [
            ProductCandidate(
                product_id=r["product_id"],
                product_name=r["product_name"],
                alias_matched=r["alias_matched"],
                similarity=float(r["sim"]),
            )
            for r in rows
        ]


def _row_to_product(row: asyncpg.Record) -> Product:
    return Product(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        duration_type=row["duration_type"],
        description=row["description"],
        country_iso=row["country_iso"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
