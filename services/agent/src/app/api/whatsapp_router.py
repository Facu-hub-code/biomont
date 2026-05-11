"""Webhook de Meta WhatsApp Business Cloud API.

GET: verificacion del webhook (`hub.challenge`).
POST: recepcion de mensajes con verificacion HMAC-SHA256.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from biomont_common.logging import get_logger

from app.agent.orchestrator import AgentOrchestrator
from app.api.dependencies import get_orchestrator
from app.integrations.whatsapp_client import verify_signature
from app.settings import WhatsAppSettings, get_whatsapp_settings

_logger = get_logger("api.whatsapp")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
    hub_verify_token: Annotated[
        str | None, Query(alias="hub.verify_token")
    ] = None,
) -> PlainTextResponse:
    settings = get_whatsapp_settings()
    expected = settings.verify_token.get_secret_value()
    if hub_mode == "subscribe" and hub_verify_token == expected and hub_challenge:
        return PlainTextResponse(hub_challenge, status_code=200)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="verification failed"
    )


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    orchestrator: Annotated[AgentOrchestrator, Depends(get_orchestrator)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict:
    raw_body = await request.body()
    settings: WhatsAppSettings = get_whatsapp_settings()
    if not verify_signature(
        raw_body=raw_body,
        signature_header=x_hub_signature_256,
        settings=settings,
    ):
        _logger.warning("whatsapp_invalid_signature", action="bad_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid signature",
        )

    payload = json.loads(raw_body or b"{}")
    processed = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {}) or {}
            messages = value.get("messages", []) or []
            for message in messages:
                if message.get("type") != "text":
                    _logger.info(
                        "whatsapp_skipped_non_text",
                        action="skipped",
                        message_type=message.get("type"),
                    )
                    continue
                from_phone = "+" + str(message.get("from", "")).lstrip("+")
                text_body = (message.get("text") or {}).get("body", "")
                if not text_body.strip():
                    continue
                await orchestrator.handle_incoming_message(
                    from_phone_e164=from_phone,
                    text_body=text_body,
                )
                processed += 1
    return {"status": "ok", "processed": processed}
