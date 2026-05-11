"""Endpoints de tickets (lectura + actualizacion de estado)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_audit, get_tickets, require_roles
from app.db.audit_repository import AuditRepository
from app.db.ticket_repository import TicketAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.tickets import TicketOut, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _to_out(row) -> TicketOut:
    return TicketOut(**asdict(row))


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    tickets: Annotated[TicketAdminRepository, Depends(get_tickets)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(open|in_progress|resolved|wont_fix)$")
    ] = None,
) -> list[TicketOut]:
    rows = await tickets.list_tickets(status_filter)
    return [_to_out(r) for r in rows]


@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    tickets: Annotated[TicketAdminRepository, Depends(get_tickets)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin", "scientist"))],
) -> TicketOut:
    existing = await tickets.get_ticket(ticket_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    fields = payload.model_dump(exclude_unset=True)
    updated = await tickets.update_ticket(
        ticket_id,
        status=fields.get("status"),
        notes=fields.get("notes"),
        assigned_to=fields.get("assigned_to"),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    await audit.record(
        actor_id=current.id,
        entity="tickets",
        entity_id=ticket_id,
        action="update",
        before={k: getattr(existing, k) for k in fields},
        after=fields,
    )
    return _to_out(updated)
