"""Persistencia y cache simple del system prompt activo."""

from __future__ import annotations

import time
from dataclasses import dataclass

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class ActiveSystemPrompt:
    version: int
    content: str


class SystemPromptRepository:
    def __init__(self, pool: DatabasePool, cache_ttl_seconds: int = 60) -> None:
        self._pool = pool
        self._cache_ttl = cache_ttl_seconds
        self._cached_at: float = 0.0
        self._cached_value: ActiveSystemPrompt | None = None

    async def get_active(self) -> ActiveSystemPrompt | None:
        now = time.monotonic()
        if (
            self._cached_value is not None
            and (now - self._cached_at) < self._cache_ttl
        ):
            return self._cached_value

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT version, content
                FROM public.system_prompts
                WHERE is_active = true
                LIMIT 1
                """
            )
        if row is None:
            self._cached_value = None
            return None

        self._cached_value = ActiveSystemPrompt(
            version=row["version"],
            content=row["content"],
        )
        self._cached_at = now
        return self._cached_value

    def invalidate(self) -> None:
        self._cached_at = 0.0
        self._cached_value = None
