"""Repositorio del backoffice para gestionar `system_prompts`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class SystemPromptRow:
    id: UUID
    version: int
    content: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime


class SystemPromptAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_prompts(self) -> list[SystemPromptRow]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM public.system_prompts ORDER BY version DESC"
            )
        return [SystemPromptRow(**dict(row)) for row in rows]

    async def create_version(self, *, content: str, created_by: UUID) -> SystemPromptRow:
        async with self._pool.transaction() as conn:
            row = await conn.fetchrow(
                "SELECT COALESCE(max(version), 0) + 1 AS next FROM public.system_prompts"
            )
            next_version = int(row["next"])
            await conn.execute(
                "UPDATE public.system_prompts SET is_active = false WHERE is_active = true"
            )
            row = await conn.fetchrow(
                """
                INSERT INTO public.system_prompts (version, content, is_active, created_by)
                VALUES ($1, $2, true, $3)
                RETURNING *
                """,
                next_version,
                content,
                created_by,
            )
        return SystemPromptRow(**dict(row))

    async def activate_version(self, version: int) -> SystemPromptRow | None:
        async with self._pool.transaction() as conn:
            await conn.execute(
                "UPDATE public.system_prompts SET is_active = false WHERE is_active = true"
            )
            row = await conn.fetchrow(
                "UPDATE public.system_prompts SET is_active = true "
                "WHERE version = $1 RETURNING *",
                version,
            )
        return SystemPromptRow(**dict(row)) if row else None
