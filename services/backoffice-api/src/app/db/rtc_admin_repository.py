"""Repositorio del backoffice para gestionar RTCs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class RtcAdminRow:
    id: UUID
    phone_e164: str
    name: str
    enabled: bool
    country_isos: list[str]
    created_at: datetime
    updated_at: datetime


class RtcAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_rtcs(self) -> list[RtcAdminRow]:
        query = """
            SELECT u.id, u.phone_e164, u.name, u.enabled,
                   u.created_at, u.updated_at,
                   COALESCE(
                       array_agg(c.country_iso) FILTER (WHERE c.country_iso IS NOT NULL),
                       ARRAY[]::char(2)[]
                   ) AS countries
            FROM public.rtc_users u
            LEFT JOIN public.rtc_user_countries c ON c.rtc_user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [self._row(row) for row in rows]

    async def get_rtc(self, rtc_id: UUID) -> RtcAdminRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.phone_e164, u.name, u.enabled,
                       u.created_at, u.updated_at,
                       COALESCE(
                           array_agg(c.country_iso)
                           FILTER (WHERE c.country_iso IS NOT NULL),
                           ARRAY[]::char(2)[]
                       ) AS countries
                FROM public.rtc_users u
                LEFT JOIN public.rtc_user_countries c ON c.rtc_user_id = u.id
                WHERE u.id = $1
                GROUP BY u.id
                """,
                rtc_id,
            )
        return self._row(row) if row else None

    async def create_rtc(
        self,
        *,
        phone_e164: str,
        name: str,
        enabled: bool,
        country_isos: list[str],
        created_by: UUID,
    ) -> UUID:
        async with self._pool.transaction() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.rtc_users (phone_e164, name, enabled, created_by)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                phone_e164,
                name,
                enabled,
                created_by,
            )
            rtc_id = row["id"]
            if country_isos:
                await conn.executemany(
                    "INSERT INTO public.rtc_user_countries (rtc_user_id, country_iso) "
                    "VALUES ($1, $2)",
                    [(rtc_id, iso.upper()) for iso in country_isos],
                )
        return rtc_id

    async def update_rtc(
        self,
        rtc_id: UUID,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        country_isos: list[str] | None = None,
    ) -> None:
        async with self._pool.transaction() as conn:
            if name is not None or enabled is not None:
                await conn.execute(
                    """
                    UPDATE public.rtc_users
                    SET name = COALESCE($2, name),
                        enabled = COALESCE($3, enabled)
                    WHERE id = $1
                    """,
                    rtc_id,
                    name,
                    enabled,
                )
            if country_isos is not None:
                await conn.execute(
                    "DELETE FROM public.rtc_user_countries WHERE rtc_user_id = $1",
                    rtc_id,
                )
                if country_isos:
                    await conn.executemany(
                        "INSERT INTO public.rtc_user_countries (rtc_user_id, country_iso) "
                        "VALUES ($1, $2)",
                        [(rtc_id, iso.upper()) for iso in country_isos],
                    )

    async def delete_rtc(self, rtc_id: UUID) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM public.rtc_users WHERE id = $1", rtc_id)

    @staticmethod
    def _row(row: object) -> RtcAdminRow:
        data = dict(row)  # type: ignore[arg-type]
        return RtcAdminRow(
            id=data["id"],
            phone_e164=data["phone_e164"],
            name=data["name"],
            enabled=data["enabled"],
            country_isos=list(data.get("countries") or []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
