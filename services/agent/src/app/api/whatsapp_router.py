"""Webhook de Meta WhatsApp Business Cloud API.

GET: verificacion del webhook (`hub.challenge`).
POST: recepcion de mensajes con verificacion HMAC-SHA256.
"""

from __future__ import annotations

import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from biomont_common.logging import get_logger

from app.agent.orchestrator import AgentOrchestrator
from app.api.dependencies import get_orchestrator
from app.integrations.whatsapp_client import verify_signature
from app.services.meta_whatsapp_webhook_parse import (
    parse_whatsapp_cloud_inbound_messages,
)
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
    token_ok = hub_verify_token is not None and secrets.compare_digest(
        hub_verify_token, expected
    )
    if hub_mode == "subscribe" and token_ok and hub_challenge:
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
    if not settings.webhook_skip_signature_verify and not verify_signature(
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
    inbound_messages = parse_whatsapp_cloud_inbound_messages(payload)
    if not inbound_messages:
        _logger.info("whatsapp_webhook_ack_no_messages", action="ack_only")
        return {"status": "ok", "processed": 0}

    if not settings.webhook_agent_enabled:
        for message in inbound_messages:
            _logger.info(
                "whatsapp_inbound_receive_only",
                action="receive_only",
                message_type=message.message_type,
                provider_message_id=message.provider_message_id,
                text_preview=message.text[:120],
            )
        return {"status": "ok", "processed": 0, "agent_enabled": False}

    processed = 0
    for message in inbound_messages:
        if message.message_type != "text":
            _logger.info(
                "whatsapp_skipped_non_text",
                action="skipped",
                message_type=message.message_type,
                provider_message_id=message.provider_message_id,
            )
            continue
        await orchestrator.handle_incoming_message(
            from_phone_e164=message.from_user_id,
            text_body=message.text,
        )
        processed += 1
    return {"status": "ok", "processed": processed}
