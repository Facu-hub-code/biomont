"""Cliente para Meta WhatsApp Business Cloud API.

Cumple `.cursor/rules/dependency-constraints.mdc`: protocolo + clase
concreta para permitir un fake en tests sin tocar el servicio.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol

import httpx

from biomont_common.logging import get_logger

from app.settings import WhatsAppSettings, get_whatsapp_settings

_logger = get_logger("integrations.whatsapp")


class WhatsAppClient(Protocol):
    async def send_text(self, *, to_phone_e164: str, body: str) -> None:
        ...


class MetaWhatsAppClient:
    """Implementacion real contra Graph API."""

    def __init__(
        self,
        *,
        settings: WhatsAppSettings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_whatsapp_settings()
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    @property
    def _messages_url(self) -> str:
        return (
            f"https://graph.facebook.com/"
            f"{self._settings.graph_api_version}/"
            f"{self._settings.phone_number_id}/messages"
        )

    async def send_text(self, *, to_phone_e164: str, body: str) -> None:
        if not body.strip():
            return
        if not self._settings.enable_outbound:
            _logger.info(
                "whatsapp_outbound_disabled",
                action="send_skipped",
            )
            return
        normalized_phone = to_phone_e164.lstrip("+")
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_phone,
            "type": "text",
            "text": {"body": body[:4096]},
        }
        headers = {
            "Authorization": (
                f"Bearer {self._settings.access_token.get_secret_value()}"
            ),
            "Content-Type": "application/json",
        }
        response = await self._http_client.post(
            self._messages_url, json=payload, headers=headers
        )
        if response.status_code >= 400:
            _logger.error(
                "whatsapp_send_failed",
                action="send_failed",
                status_code=response.status_code,
            )
            response.raise_for_status()
        _logger.info(
            "whatsapp_send_ok",
            action="send_ok",
            status_code=response.status_code,
        )


def verify_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    settings: WhatsAppSettings | None = None,
) -> bool:
    """Verifica la firma HMAC-SHA256 del webhook (`X-Hub-Signature-256`)."""

    if not signature_header or not signature_header.startswith("sha256="):
        return False
    cfg = settings or get_whatsapp_settings()
    digest = hmac.new(
        cfg.app_secret.get_secret_value().encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header)
