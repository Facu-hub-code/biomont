"""Endpoints CRUD de RTCs habilitados."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_audit,
    get_rtcs,
    require_roles,
)
from app.db.audit_repository import AuditRepository
from app.db.rtc_admin_repository import RtcAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.rtcs import RtcUserCreate, RtcUserOut, RtcUserUpdate

router = APIRouter(prefix="/rtcs", tags=["rtcs"])


def _to_out(row) -> RtcUserOut:
    return RtcUserOut(**asdict(row))


@router.get("", response_model=list[RtcUserOut])
async def list_rtcs(
    rtcs: Annotated[RtcAdminRepository, Depends(get_rtcs)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> list[RtcUserOut]:
    rows = await rtcs.list_rtcs()
    return [_to_out(r) for r in rows]


@router.post(
    "",
    response_model=RtcUserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_rtc(
    payload: RtcUserCreate,
    rtcs: Annotated[RtcAdminRepository, Depends(get_rtcs)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> RtcUserOut:
    rtc_id = await rtcs.create_rtc(
        phone_e164=payload.phone_e164,
        name=payload.name,
        enabled=payload.enabled,
        country_isos=payload.country_isos,
        created_by=current.id,
    )
    row = await rtcs.get_rtc(rtc_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    await audit.record(
        actor_id=current.id,
        entity="rtc_users",
        entity_id=rtc_id,
        action="create",
        after=payload.model_dump(),
    )
    return _to_out(row)


@router.patch("/{rtc_id}", response_model=RtcUserOut)
async def update_rtc(
    rtc_id: UUID,
    payload: RtcUserUpdate,
    rtcs: Annotated[RtcAdminRepository, Depends(get_rtcs)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> RtcUserOut:
    existing = await rtcs.get_rtc(rtc_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    fields = payload.model_dump(exclude_unset=True)
    await rtcs.update_rtc(
        rtc_id,
        name=fields.get("name"),
        enabled=fields.get("enabled"),
        country_isos=fields.get("country_isos"),
    )
    row = await rtcs.get_rtc(rtc_id)
    await audit.record(
        actor_id=current.id,
        entity="rtc_users",
        entity_id=rtc_id,
        action="update",
        before={k: getattr(existing, k) for k in fields},
        after=fields,
    )
    return _to_out(row)  # type: ignore[arg-type]


@router.delete("/{rtc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rtc(
    rtc_id: UUID,
    rtcs: Annotated[RtcAdminRepository, Depends(get_rtcs)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> None:
    existing = await rtcs.get_rtc(rtc_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await rtcs.delete_rtc(rtc_id)
    await audit.record(
        actor_id=current.id,
        entity="rtc_users",
        entity_id=rtc_id,
        action="delete",
        before=asdict(existing),
    )
