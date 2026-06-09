"""Procesamiento asincronico de mensajes WhatsApp tras ack rapido al webhook."""

from __future__ import annotations

from biomont_common.db.whatsapp_inbound_repository import WhatsappInboundRepository
from biomont_common.logging import get_logger

from app.agent.orchestrator import AgentOrchestrator
from app.services.meta_whatsapp_webhook_parse import InboundWhatsAppMessage

_logger = get_logger("services.whatsapp_inbound_processor")


async def process_inbound_whatsapp_message(
    *,
    message: InboundWhatsAppMessage,
    orchestrator: AgentOrchestrator,
    inbound_repository: WhatsappInboundRepository,
) -> None:
    wamid = message.provider_message_id
    if wamid:
        claimed = await inbound_repository.try_claim(
            provider_message_id=wamid,
            from_phone_e164=message.from_user_id,
            message_type=message.message_type,
        )
        if not claimed:
            _logger.info(
                "whatsapp_inbound_deduped",
                action="skipped_duplicate",
                provider_message_id=wamid,
            )
            return
    else:
        _logger.warning(
            "whatsapp_inbound_missing_wamid",
            action="process_without_dedup",
            from_phone_hash=message.from_user_id[-4:],
        )

    try:
        await orchestrator.handle_incoming_message(
            from_phone_e164=message.from_user_id,
            text_body=message.text,
        )
    except Exception:
        _logger.exception(
            "whatsapp_inbound_process_failed",
            action="process_failed",
            provider_message_id=wamid,
        )
        raise

    if wamid:
        await inbound_repository.mark_processed(wamid)
