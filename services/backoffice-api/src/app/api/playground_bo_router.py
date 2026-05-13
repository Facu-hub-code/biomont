"""Playground: prueba del agente vía proxy al servicio interno."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import require_roles
from app.schemas.auth import CurrentUser
from app.schemas.conversations import PlaygroundProxyIn, PlaygroundProxyOut
from app.services.agent_playground_client import PlaygroundAgentError, forward_playground_message
from app.settings import get_backoffice_settings

router = APIRouter(prefix="/playground", tags=["playground"])


@router.post("/messages", response_model=PlaygroundProxyOut)
async def post_playground_message(
    body: PlaygroundProxyIn,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist"))],
) -> PlaygroundProxyOut:
    settings = get_backoffice_settings()
    secret = settings.agent_playground_secret
    if secret is None or not secret.get_secret_value().strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="playground not configured (missing AGENT_PLAYGROUND_SECRET)",
        )
    request_id = request.headers.get("x-request-id") or str(uuid4())
    try:
        return await forward_playground_message(
            agent_base_url=settings.agent_internal_base_url,
            secret=secret.get_secret_value(),
            rtc_user_id=body.rtc_user_id,
            text=body.text.strip(),
            request_id=request_id,
        )
    except PlaygroundAgentError as exc:
        code = exc.status_code
        if code == 401:
            code = 502
        raise HTTPException(status_code=code, detail=exc.detail) from exc
