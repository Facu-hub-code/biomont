"""Tests HTTP del router interno de playground."""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.agent.orchestrator import AgentOrchestrator, HandleResult
from app.api.playground_router import get_orchestrator, router as playground_router
from app.settings import get_agent_settings


@pytest.fixture
def playground_env():
    os.environ["AGENT_PLAYGROUND_SECRET"] = "unit-test-playground-secret"
    get_agent_settings.cache_clear()
    yield
    del os.environ["AGENT_PLAYGROUND_SECRET"]
    get_agent_settings.cache_clear()


def _minimal_app(orchestrator: AgentOrchestrator) -> FastAPI:
    app = FastAPI()
    app.include_router(playground_router)

    def _orch(_: Request) -> AgentOrchestrator:
        return orchestrator

    app.dependency_overrides[get_orchestrator] = _orch
    return app


@pytest.mark.asyncio
async def test_playground_happy_path(playground_env) -> None:
    orch = MagicMock(spec=AgentOrchestrator)
    orch.handle_playground_message = AsyncMock(
        return_value=HandleResult(decision="answered", reply_text="hola", ticket_id=None),
    )
    app = _minimal_app(orch)
    rtc_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/internal/playground/messages",
            json={"rtc_user_id": str(rtc_id), "text": "ping"},
            headers={"X-Playground-Secret": "unit-test-playground-secret"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "answered"
    assert body["reply_text"] == "hola"
    orch.handle_playground_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_playground_rejects_wrong_secret(playground_env) -> None:
    orch = MagicMock(spec=AgentOrchestrator)
    orch.handle_playground_message = AsyncMock()
    app = _minimal_app(orch)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/internal/playground/messages",
            json={"rtc_user_id": str(uuid.uuid4()), "text": "x"},
            headers={"X-Playground-Secret": "wrong"},
        )
    assert r.status_code == 401
    orch.handle_playground_message.assert_not_called()


@pytest.mark.asyncio
async def test_playground_forbidden_rtc(playground_env) -> None:
    from app.agent.orchestrator import PlaygroundRtcForbiddenError

    orch = MagicMock(spec=AgentOrchestrator)
    orch.handle_playground_message = AsyncMock(side_effect=PlaygroundRtcForbiddenError())
    app = _minimal_app(orch)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/internal/playground/messages",
            json={"rtc_user_id": str(uuid.uuid4()), "text": "x"},
            headers={"X-Playground-Secret": "unit-test-playground-secret"},
        )
    assert r.status_code == 403
