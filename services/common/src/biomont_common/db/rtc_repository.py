"""Repositorio sobre RTCs y sus paises habilitados."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class RtcUser:
    id: UUID
    phone_e164: str
    name: str
    enabled: bool
    countries: list[str]


class RtcRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def find_by_phone(self, phone_e164: str) -> RtcUser | None:
        query = """
            SELECT u.id, u.phone_e164, u.name, u.enabled,
                   COALESCE(
                       array_agg(c.country_iso) FILTER (WHERE c.country_iso IS NOT NULL),
                       ARRAY[]::char(2)[]
                   ) AS countries
            FROM public.rtc_users u
            LEFT JOIN public.rtc_user_countries c
                ON c.rtc_user_id = u.id
            WHERE u.phone_e164 = $1
            GROUP BY u.id
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, phone_e164)
        if row is None:
            return None
        return RtcUser(
            id=row["id"],
            phone_e164=row["phone_e164"],
            name=row["name"],
            enabled=row["enabled"],
            countries=list(row["countries"] or []),
        )
