"""Lectura/actualizacion de tickets desde el backoffice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class TicketRow:
    id: UUID
    conversation_id: UUID | None
    message_id: UUID | None
    type: str
    status: str
    summary: str
    notes: str | None
    assigned_to: UUID | None
    created_at: datetime
    updated_at: datetime


class TicketAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_tickets(self, status: str | None = None) -> list[TicketRow]:
        query = "SELECT * FROM public.tickets"
        args: list[object] = []
        if status:
            query += " WHERE status = $1"
            args.append(status)
        query += " ORDER BY created_at DESC"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [TicketRow(**dict(row)) for row in rows]

    async def get_ticket(self, ticket_id: UUID) -> TicketRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.tickets WHERE id = $1", ticket_id
            )
        return TicketRow(**dict(row)) if row else None

    async def update_ticket(
        self,
        ticket_id: UUID,
        *,
        status: str | None = None,
        notes: str | None = None,
        assigned_to: UUID | None = None,
    ) -> TicketRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.tickets
                SET status = COALESCE($2, status),
                    notes = COALESCE($3, notes),
                    assigned_to = COALESCE($4, assigned_to)
                WHERE id = $1
                RETURNING *
                """,
                ticket_id,
                status,
                notes,
                assigned_to,
            )
        return TicketRow(**dict(row)) if row else None
