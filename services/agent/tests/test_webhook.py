"""Tests del webhook de Meta: firma HMAC + ack rapido + dedupe wamid."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.agent.orchestrator import HandleResult
from app.api.dependencies import get_orchestrator, get_whatsapp_inbound_repository
from app.api.whatsapp_router import router as whatsapp_router
from app.settings import get_whatsapp_settings


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def handle_incoming_message(self, *, from_phone_e164: str, text_body: str):
        self.calls.append({"phone": from_phone_e164, "text": text_body})
        return HandleResult(decision="answered", reply_text="ok")


class FakeInboundRepository:
    def __init__(self) -> None:
        self.claimed: set[str] = set()
        self.processed: set[str] = set()

    async def try_claim(
        self,
        *,
        provider_message_id: str,
        from_phone_e164: str,
        message_type: str,
    ) -> bool:
        if provider_message_id in self.claimed:
            return False
        self.claimed.add(provider_message_id)
        return True

    async def mark_processed(self, provider_message_id: str) -> None:
        self.processed.add(provider_message_id)


def _build_app(
    stub: StubOrchestrator,
    inbound_repo: FakeInboundRepository | None = None,
) -> FastAPI:
    repo = inbound_repo or FakeInboundRepository()
    app = FastAPI()
    app.include_router(whatsapp_router)
    app.dependency_overrides[get_orchestrator] = lambda: stub
    app.dependency_overrides[get_whatsapp_inbound_repository] = lambda: repo
    return app


def _text_payload(*, wamid: str = "wamid.test.001") -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": "51999000111",
                                    "type": "text",
                                    "text": {"body": "Hola agente"},
                                }
                            ]
                        },
                    }
                ]
            }
        ],
    }


def _sign(body: bytes) -> str:
    secret = get_whatsapp_settings().app_secret.get_secret_value().encode()
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature() -> None:
    stub = StubOrchestrator()
    app = _build_app(stub)
    payload = {"entry": []}
    body = json.dumps(payload).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/whatsapp/webhook",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=invalid"},
        )
    assert response.status_code == 401
    assert stub.calls == []


@pytest.mark.asyncio
async def test_webhook_enqueues_text_message_with_valid_signature() -> None:
    stub = StubOrchestrator()
    app = _build_app(stub)
    body = json.dumps(_text_payload()).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/whatsapp/webhook",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body)},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "enqueued": 1}
    assert stub.calls == [
        {"phone": "+51999000111", "text": "Hola agente"}
    ]


@pytest.mark.asyncio
async def test_webhook_dedupes_duplicate_wamid() -> None:
    stub = StubOrchestrator()
    repo = FakeInboundRepository()
    app = _build_app(stub, repo)
    body = json.dumps(_text_payload(wamid="wamid.duplicate.001")).encode()
    headers = {"X-Hub-Signature-256": _sign(body)}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post("/whatsapp/webhook", content=body, headers=headers)
        second = await client.post("/whatsapp/webhook", content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["enqueued"] == 1
    assert second.json()["enqueued"] == 1
    assert len(stub.calls) == 1


@pytest.mark.asyncio
async def test_webhook_verify_get_returns_challenge() -> None:
    stub = StubOrchestrator()
    app = _build_app(stub)
    settings = get_whatsapp_settings()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "abc123",
                "hub.verify_token": settings.verify_token.get_secret_value(),
            },
        )
    assert response.status_code == 200
    assert response.text == "abc123"


@pytest.mark.asyncio
async def test_webhook_receive_only_skips_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_WEBHOOK_AGENT_ENABLED", "false")
    get_whatsapp_settings.cache_clear()

    stub = StubOrchestrator()
    app = _build_app(stub)
    body = json.dumps(_text_payload()).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/whatsapp/webhook",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body)},
        )
    get_whatsapp_settings.cache_clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "enqueued": 0, "agent_enabled": False}
    assert stub.calls == []


@pytest.mark.asyncio
async def test_webhook_verify_get_rejects_bad_token() -> None:
    stub = StubOrchestrator()
    app = _build_app(stub)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "abc",
                "hub.verify_token": "wrong",
            },
        )
    assert response.status_code == 403
