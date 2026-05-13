"""Tests HTTP de conversaciones y proxy playground (sin DB real)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.api.playground_bo_router as playground_bo_module
from app.api.conversations_router import router as conversations_router
from app.api.dependencies import get_conversations, get_current_user
from app.api.playground_bo_router import router as playground_bo_router
from app.db.conversation_admin_repository import ConversationListRow, ConversationMessageRow
from app.schemas.auth import CurrentUser
from app.schemas.conversations import PlaygroundProxyOut
from app.settings import get_backoffice_settings


@pytest.fixture()
def admin_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="a@example.com",
        name="Admin",
        role="admin",
    )


class FakeConversationRepo:
    def __init__(self) -> None:
        self.conversations: list[ConversationListRow] = []
        self.messages: dict[uuid.UUID, list[ConversationMessageRow]] = {}

    async def list_conversations(self, *, limit: int = 200) -> list[ConversationListRow]:
        return self.conversations

    async def list_messages(
        self, conversation_id: uuid.UUID, *, limit: int = 500
    ) -> list[ConversationMessageRow]:
        return self.messages.get(conversation_id, [])


def _conv_app(fake_repo: FakeConversationRepo, user: CurrentUser) -> FastAPI:
    app = FastAPI()
    app.include_router(conversations_router)

    async def _user():
        return user

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_conversations] = lambda: fake_repo
    return app


@pytest.mark.asyncio
async def test_list_conversations_returns_rows(admin_user) -> None:
    cid = uuid.uuid4()
    rtc_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_repo = FakeConversationRepo()
    fake_repo.conversations = [
        ConversationListRow(
            id=cid,
            rtc_user_id=rtc_id,
            rtc_name="RTC Uno",
            phone_e164="+51999001111",
            started_at=now,
            last_message_at=now,
            last_preview="hola",
        )
    ]
    app = _conv_app(fake_repo, admin_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/conversations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["rtc_name"] == "RTC Uno"


@pytest.mark.asyncio
async def test_list_messages_returns_ordered(admin_user) -> None:
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_repo = FakeConversationRepo()
    m1 = ConversationMessageRow(
        id=uuid.uuid4(),
        conversation_id=cid,
        role="user",
        content="ping",
        created_at=now,
    )
    m2 = ConversationMessageRow(
        id=uuid.uuid4(),
        conversation_id=cid,
        role="assistant",
        content="pong",
        created_at=now,
    )
    fake_repo.messages[cid] = [m1, m2]
    app = _conv_app(fake_repo, admin_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/conversations/{cid}/messages")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["content"] == "ping"


@pytest.mark.asyncio
async def test_playground_proxy_success(admin_user, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AGENT_PLAYGROUND_SECRET",
        "shared-secret-for-test-shared-secret-for-test",
    )
    monkeypatch.setenv("AGENT_INTERNAL_BASE_URL", "http://agent.invalid")
    get_backoffice_settings.cache_clear()

    async def _fake_forward(**_kwargs):
        return PlaygroundProxyOut(
            decision="answered", reply_text="ok", ticket_id=None
        )

    monkeypatch.setattr(
        playground_bo_module,
        "forward_playground_message",
        _fake_forward,
    )

    app = FastAPI()
    app.include_router(playground_bo_router)

    async def _user():
        return admin_user

    app.dependency_overrides[get_current_user] = _user

    rtc_id = uuid.uuid4()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/playground/messages",
                json={"rtc_user_id": str(rtc_id), "text": "hola"},
            )
        assert r.status_code == 200
        assert r.json()["reply_text"] == "ok"
    finally:
        monkeypatch.delenv("AGENT_PLAYGROUND_SECRET", raising=False)
        get_backoffice_settings.cache_clear()


@pytest.mark.asyncio
async def test_playground_proxy_503_when_unconfigured(admin_user, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_PLAYGROUND_SECRET", raising=False)
    get_backoffice_settings.cache_clear()

    app = FastAPI()
    app.include_router(playground_bo_router)

    async def _user():
        return admin_user

    app.dependency_overrides[get_current_user] = _user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/playground/messages",
            json={"rtc_user_id": str(uuid.uuid4()), "text": "hola"},
        )
    assert r.status_code == 503
