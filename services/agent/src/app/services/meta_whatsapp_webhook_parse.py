"""Parseo del payload nativo de Meta WhatsApp Cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from biomont_common.logging import get_logger

_logger = get_logger("services.meta_whatsapp_webhook_parse")

_NON_TEXT_PLACEHOLDERS: dict[str, str] = {
    "audio": "[audio]",
    "image": "[imagen]",
    "video": "[video]",
    "document": "[documento]",
    "sticker": "[sticker]",
    "location": "[ubicacion]",
    "contacts": "[contacto]",
    "interactive": "[interactivo]",
    "button": "[boton]",
    "reaction": "[reaccion]",
}


@dataclass(slots=True)
class InboundWhatsAppMessage:
    provider: str
    from_user_id: str
    to_business_phone: str | None
    text: str
    provider_message_id: str | None
    message_type: str
    raw: dict[str, Any]


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return f"+{digits}" if digits else None


def _extract_text(message: dict[str, Any]) -> str | None:
    message_type = str(message.get("type") or "")
    if message_type == "text":
        body = ((message.get("text") or {}).get("body") or "").strip()
        return body or None
    if message_type == "system":
        return None
    return _NON_TEXT_PLACEHOLDERS.get(message_type, f"[{message_type or 'desconocido'}]")


def parse_whatsapp_cloud_inbound_messages(
    payload: dict[str, Any],
) -> list[InboundWhatsAppMessage]:
    """Normaliza mensajes de usuario desde el JSON nativo de Meta."""

    if payload.get("object") != "whatsapp_business_account":
        _logger.warning(
            "whatsapp_unexpected_object",
            action="parse_skipped",
            object_type=payload.get("object"),
        )
        return []

    parsed: list[InboundWhatsAppMessage] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value", {}) or {}
            metadata = value.get("metadata", {}) or {}
            to_business_phone = _normalize_phone(
                metadata.get("display_phone_number")
            )
            messages = value.get("messages", []) or []
            if not messages:
                continue
            if len(messages) > 1:
                _logger.warning(
                    "whatsapp_multiple_messages_in_payload",
                    action="parse_first_only",
                    count=len(messages),
                )
            for message in messages[:1]:
                message_type = str(message.get("type") or "")
                if message_type == "system":
                    _logger.info(
                        "whatsapp_skipped_system",
                        action="skipped",
                        message_type=message_type,
                    )
                    continue
                text = _extract_text(message)
                if not text:
                    continue
                from_user_id = _normalize_phone(message.get("from"))
                if not from_user_id:
                    continue
                parsed.append(
                    InboundWhatsAppMessage(
                        provider="meta",
                        from_user_id=from_user_id,
                        to_business_phone=to_business_phone,
                        text=text,
                        provider_message_id=message.get("id"),
                        message_type=message_type,
                        raw=message,
                    )
                )
    return parsed
