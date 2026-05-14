"""Endpoints de auditoria para decisiones del agente."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from biomont_common.db.agent_decision_repository import AgentDecisionRepository

from app.api.dependencies import get_agent_decisions, require_roles
from app.schemas.agent_decisions import (
    AgentDecisionDetail,
    AgentDecisionKind,
    AgentDecisionListItem,
    AgentDecisionListResponse,
)
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/agent-decisions", tags=["agent-decisions"])


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(1, page)
    safe_page_size = min(max(1, page_size), 100)
    return safe_page, safe_page_size


def _only_digits(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


@router.get("", response_model=AgentDecisionListResponse)
async def list_agent_decisions(
    decisions: AgentDecisionRepository = Depends(get_agent_decisions),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
    decision: AgentDecisionKind | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    phone: str | None = None,
    conversation_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AgentDecisionListResponse:
    safe_page, safe_size = _pagination(page, page_size)
    total, rows = await decisions.list_decisions(
        page=safe_page,
        page_size=safe_size,
        decision=decision,
        date_from=date_from,
        date_to=date_to,
        phone_digits=_only_digits(phone),
        conversation_id=conversation_id,
    )
    return AgentDecisionListResponse(
        items=[AgentDecisionListItem(**asdict(row)) for row in rows],
        page=safe_page,
        page_size=safe_size,
        total=total,
    )


@router.get("/{decision_id}", response_model=AgentDecisionDetail)
async def get_agent_decision(
    decision_id: UUID,
    decisions: AgentDecisionRepository = Depends(get_agent_decisions),
    _: CurrentUser = Depends(require_roles("admin", "scientist", "viewer")),
) -> AgentDecisionDetail:
    row = await decisions.get_decision(decision_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return AgentDecisionDetail(**asdict(row))
