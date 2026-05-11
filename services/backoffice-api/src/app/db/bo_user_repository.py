"""Persistencia de usuarios del backoffice."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class BoUserRow:
    id: UUID
    email: str
    password_hash: str
    name: str
    role: str
    is_active: bool


class BoUserRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def find_by_email(self, email: str) -> BoUserRow | None:
        query = """
            SELECT id, email, password_hash, name, role, is_active
            FROM public.bo_users
            WHERE lower(email) = lower($1)
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, email)
        return BoUserRow(**dict(row)) if row else None

    async def find_by_id(self, user_id: UUID) -> BoUserRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, password_hash, name, role, is_active "
                "FROM public.bo_users WHERE id = $1",
                user_id,
            )
        return BoUserRow(**dict(row)) if row else None
