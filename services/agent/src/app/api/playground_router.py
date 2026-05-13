"""Endpoint interno para mensajes del playground (backoffice)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentOrchestrator, PlaygroundRtcForbiddenError
from app.settings import get_agent_settings

router = APIRouter(prefix="/internal/playground", tags=["playground"])


class PlaygroundMessageIn(BaseModel):
    rtc_user_id: UUID
    text: str = Field(..., min_length=1, max_length=8000)


class PlaygroundMessageOut(BaseModel):
    decision: str
    reply_text: str
    ticket_id: str | None = None


def get_orchestrator(request: Request) -> AgentOrchestrator:
    return request.app.state.orchestrator


@router.post("/messages", response_model=PlaygroundMessageOut)
async def post_playground_message(
    body: PlaygroundMessageIn,
    request: Request,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    x_playground_secret: Annotated[str | None, Header()] = None,
) -> PlaygroundMessageOut:
    settings = get_agent_settings()
    expected = settings.playground_secret
    if expected is None or not expected.get_secret_value().strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="playground disabled",
        )
    if not x_playground_secret or x_playground_secret != expected.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid playground secret",
        )
    try:
        result = await orchestrator.handle_playground_message(
            rtc_user_id=body.rtc_user_id,
            text_body=body.text.strip(),
        )
    except PlaygroundRtcForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="rtc not found or disabled",
        ) from exc
    return PlaygroundMessageOut(
        decision=result.decision,
        reply_text=result.reply_text,
        ticket_id=result.ticket_id,
    )
