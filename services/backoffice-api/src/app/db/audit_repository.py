"""Audit log de cambios en el backoffice."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from biomont_common.db.pool import DatabasePool


def audit_json_default(value: object) -> object:
    """Convierte tipos de dominio a JSON nativo para `bo_audit_log`."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_audit_payload(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, default=audit_json_default)


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
                dumps_audit_payload(before),
                dumps_audit_payload(after),
            )
