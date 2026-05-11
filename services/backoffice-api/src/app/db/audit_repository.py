"""Audit log de cambios en el backoffice."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from biomont_common.db.pool import DatabasePool


class AuditRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def record(
        self,
        *,
        actor_id: UUID | None,
        entity: str,
        entity_id: UUID | None,
        action: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.bo_audit_log
                    (actor_id, entity, entity_id, action, before, after)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                """,
                actor_id,
                entity,
                entity_id,
                action,
                json.dumps(before) if before is not None else None,
                json.dumps(after) if after is not None else None,
            )
