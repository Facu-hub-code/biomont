"""Tests del webhook de Meta: firma HMAC + ruteo a orchestrator."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.agent.orchestrator import HandleResult
from app.api.dependencies import get_orchestrator
from app.api.whatsapp_router import router as whatsapp_router
from app.settings import get_whatsapp_settings


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def handle_incoming_message(self, *, from_phone_e164: str, text_body: str):
        self.calls.append({"phone": from_phone_e164, "text": text_body})
        return HandleResult(decision="answered", reply_text="ok")


def _build_app(stub: StubOrchestrator) -> FastAPI:
    app = FastAPI()
    app.include_router(whatsapp_router)
    app.dependency_overrides[get_orchestrator] = lambda: stub
    return app


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
async def test_webhook_processes_text_message_with_valid_signature() -> None:
    stub = StubOrchestrator()
    app = _build_app(stub)
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "51999000111",
                                    "type": "text",
                                    "text": {"body": "Hola agente"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/whatsapp/webhook",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body)},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1}
    assert stub.calls == [
        {"phone": "+51999000111", "text": "Hola agente"}
    ]


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
