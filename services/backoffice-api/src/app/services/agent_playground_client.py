"""Proxy al agente para mensajes del playground (misma persistencia, sin WhatsApp)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from biomont_common.logging import get_logger

from app.schemas.conversations import PlaygroundProxyOut

_logger = get_logger("backoffice.playground_proxy")


class PlaygroundAgentError(Exception):
    """Error al invocar el agente interno."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def forward_playground_message(
    *,
    agent_base_url: str,
    secret: str,
    rtc_user_id: UUID,
    text: str,
    request_id: str | None,
) -> PlaygroundProxyOut:
    base = agent_base_url.rstrip("/")
    url = f"{base}/internal/playground/messages"
    headers: dict[str, str] = {
        "X-Playground-Secret": secret,
        "Content-Type": "application/json",
    }
    if request_id:
        headers["X-Request-Id"] = request_id
    payload = {"rtc_user_id": str(rtc_user_id), "text": text}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            _logger.warning(
                "playground_agent_unreachable",
                action="request_error",
                error=str(exc),
            )
            raise PlaygroundAgentError(
                status_code=502,
                detail="agent service unreachable",
            ) from exc

    if response.status_code >= 400:
        detail = _parse_error_detail(response)
        _logger.warning(
            "playground_agent_error",
            action="agent_error",
            status=response.status_code,
            detail=detail[:200],
        )
        raise PlaygroundAgentError(status_code=response.status_code, detail=detail)

    data: dict[str, Any] = response.json()
    return PlaygroundProxyOut(
        decision=str(data["decision"]),
        reply_text=str(data["reply_text"]),
        ticket_id=data.get("ticket_id"),
    )


def _parse_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        return response.text or response.reason_phrase
    if isinstance(body, dict):
        raw = body.get("detail")
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            return str(raw)
    return str(body)
