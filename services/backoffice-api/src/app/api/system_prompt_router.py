"""Endpoints para gestionar el system prompt activo y su historial."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_audit,
    get_prompts,
    require_roles,
)
from app.db.audit_repository import AuditRepository
from app.db.system_prompt_admin_repository import SystemPromptAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.system_prompt import SystemPromptCreate, SystemPromptOut

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


def _to_out(row) -> SystemPromptOut:
    return SystemPromptOut(**asdict(row))


@router.get("", response_model=list[SystemPromptOut])
async def list_prompts(
    prompts: Annotated[SystemPromptAdminRepository, Depends(get_prompts)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> list[SystemPromptOut]:
    rows = await prompts.list_prompts()
    return [_to_out(r) for r in rows]


@router.post(
    "",
    response_model=SystemPromptOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt(
    payload: SystemPromptCreate,
    prompts: Annotated[SystemPromptAdminRepository, Depends(get_prompts)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> SystemPromptOut:
    new_row = await prompts.create_version(
        content=payload.content,
        created_by=current.id,
    )
    await audit.record(
        actor_id=current.id,
        entity="system_prompts",
        entity_id=new_row.id,
        action="create_version",
        after={"version": new_row.version},
    )
    return _to_out(new_row)


@router.post("/{version}/activate", response_model=SystemPromptOut)
async def activate_prompt(
    version: int,
    prompts: Annotated[SystemPromptAdminRepository, Depends(get_prompts)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> SystemPromptOut:
    row = await prompts.activate_version(version)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="system_prompts",
        entity_id=row.id,
        action="activate",
        after={"version": row.version},
    )
    return _to_out(row)
