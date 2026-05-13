"""Listado de conversaciones y mensajes (solo lectura)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_conversations, require_roles
from app.db.conversation_admin_repository import ConversationAdminRepository
from app.schemas.auth import CurrentUser
from app.schemas.conversations import ConversationMessageOut, ConversationSummaryOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_summary(row) -> ConversationSummaryOut:
    d = asdict(row)
    return ConversationSummaryOut(**d)


@router.get("", response_model=list[ConversationSummaryOut])
async def list_conversations(
    repo: Annotated[ConversationAdminRepository, Depends(get_conversations)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> list[ConversationSummaryOut]:
    rows = await repo.list_conversations()
    return [_to_summary(r) for r in rows]


@router.get(
    "/{conversation_id}/messages",
    response_model=list[ConversationMessageOut],
)
async def list_conversation_messages(
    conversation_id: UUID,
    repo: Annotated[ConversationAdminRepository, Depends(get_conversations)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> list[ConversationMessageOut]:
    rows = await repo.list_messages(conversation_id)
    return [
        ConversationMessageOut(
            id=r.id,
            conversation_id=r.conversation_id,
            role=r.role,
            content=r.content,
            created_at=r.created_at,
        )
        for r in rows
    ]
