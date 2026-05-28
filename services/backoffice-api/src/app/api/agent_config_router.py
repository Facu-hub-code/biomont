"""Endpoints para configuracion del agente (spec 008)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_agent_config, get_audit, require_roles
from app.db.agent_config_admin_repository import (
    AgentConfigAdminRepository,
    AgentConfigVersionRow,
    AgentIntentConfigRow,
)
from app.db.audit_repository import AuditRepository
from app.schemas.agent_config import (
    AgentConfigVersionCreate,
    AgentConfigVersionOut,
    IntentConfigOut,
)
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/agent-config", tags=["agent-config"])


def _intent_out(row: AgentIntentConfigRow) -> IntentConfigOut:
    return IntentConfigOut(
        id=row.id,
        intent_slug=row.intent_slug,
        display_label=row.display_label,
        classifier_hint=row.classifier_hint,
        document_kinds=list(row.document_kinds),
        sort_order=row.sort_order,
        is_enabled=row.is_enabled,
    )


def _version_out(row: AgentConfigVersionRow) -> AgentConfigVersionOut:
    return AgentConfigVersionOut(
        id=row.id,
        version=row.version,
        is_active=row.is_active,
        top_k=row.top_k,
        candidate_k=row.candidate_k,
        full_corpus_for_all_intents=row.full_corpus_for_all_intents,
        classifier_preamble=row.classifier_preamble,
        created_at=row.created_at,
        intents=[_intent_out(i) for i in row.intents],
    )


@router.get("/versions", response_model=list[AgentConfigVersionOut])
async def list_versions(
    repo: Annotated[AgentConfigAdminRepository, Depends(get_agent_config)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> list[AgentConfigVersionOut]:
    rows = await repo.list_versions()
    return [_version_out(r) for r in rows]


@router.get("/active", response_model=AgentConfigVersionOut)
async def get_active(
    repo: Annotated[AgentConfigAdminRepository, Depends(get_agent_config)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> AgentConfigVersionOut:
    row = await repo.get_active()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no hay configuracion activa",
        )
    return _version_out(row)


@router.post(
    "/versions",
    response_model=AgentConfigVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    payload: AgentConfigVersionCreate,
    repo: Annotated[AgentConfigAdminRepository, Depends(get_agent_config)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> AgentConfigVersionOut:
    try:
        row = await repo.create_version(
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
            full_corpus_for_all_intents=payload.full_corpus_for_all_intents,
            classifier_preamble=payload.classifier_preamble,
            intents=[i.model_dump() for i in payload.intents],
            created_by=current.id,
            activate=payload.activate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await audit.record(
        actor_id=current.id,
        entity="agent_config_versions",
        entity_id=row.id,
        action="create_version",
        after={"version": row.version, "top_k": row.top_k},
    )
    return _version_out(row)


@router.post("/versions/{version}/activate", response_model=AgentConfigVersionOut)
async def activate_version(
    version: int,
    repo: Annotated[AgentConfigAdminRepository, Depends(get_agent_config)],
    audit: Annotated[AuditRepository, Depends(get_audit)],
    current: Annotated[CurrentUser, Depends(require_roles("admin"))],
) -> AgentConfigVersionOut:
    row = await repo.activate_version(version)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await audit.record(
        actor_id=current.id,
        entity="agent_config_versions",
        entity_id=row.id,
        action="activate",
        after={"version": row.version},
    )
    return _version_out(row)
