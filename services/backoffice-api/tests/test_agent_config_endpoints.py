"""Tests HTTP de /agent-config (spec 008)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.agent_config_router import router as agent_config_router
from app.api.dependencies import get_agent_config, get_audit, get_current_user
from app.schemas.auth import CurrentUser
from biomont_common.schemas.agent_graph import Intent


@dataclass
class _FakeIntentRow:
    id: uuid.UUID
    config_version_id: uuid.UUID
    intent_slug: str
    display_label: str
    classifier_hint: str
    document_kinds: list[str]
    sort_order: int
    is_enabled: bool


@dataclass
class _FakeVersionRow:
    id: uuid.UUID
    version: int
    is_active: bool
    top_k: int
    candidate_k: int
    full_corpus_for_all_intents: bool
    classifier_preamble: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    intents: list[_FakeIntentRow]


class FakeAgentConfigAdminRepository:
    def __init__(self) -> None:
        self._versions: list[_FakeVersionRow] = []

    async def list_versions(self) -> list:
        return self._versions

    async def get_active(self):
        for v in self._versions:
            if v.is_active:
                return v
        return None

    async def create_version(self, **kwargs):
        next_v = len(self._versions) + 1
        vid = uuid.uuid4()
        intents = [
            _FakeIntentRow(
                id=uuid.uuid4(),
                config_version_id=vid,
                intent_slug=i["intent_slug"],
                display_label=i["display_label"],
                classifier_hint=i["classifier_hint"],
                document_kinds=list(i.get("document_kinds") or []),
                sort_order=int(i.get("sort_order") or 0),
                is_enabled=bool(i.get("is_enabled", True)),
            )
            for i in kwargs["intents"]
        ]
        row = _FakeVersionRow(
            id=vid,
            version=next_v,
            is_active=kwargs.get("activate", True),
            top_k=kwargs["top_k"],
            candidate_k=kwargs["candidate_k"],
            full_corpus_for_all_intents=kwargs["full_corpus_for_all_intents"],
            classifier_preamble=kwargs.get("classifier_preamble"),
            created_by=kwargs["created_by"],
            created_at=datetime.now(timezone.utc),
            intents=intents,
        )
        if row.is_active:
            for v in self._versions:
                v.is_active = False
        self._versions.append(row)
        return row

    async def activate_version(self, version: int):
        target = None
        for v in self._versions:
            v.is_active = v.version == version
            if v.version == version:
                target = v
        return target


class _FakeAudit:
    async def record(self, **kwargs):
        return None


def _default_intents() -> list[dict]:
    return [
        {
            "intent_slug": Intent.dosage_question.value,
            "display_label": "Dosis",
            "classifier_hint": "dosis",
            "document_kinds": ["bitacora", "ficha_tecnica", "balotario"],
            "sort_order": 10,
            "is_enabled": True,
        }
    ]


def _build_app(repo: FakeAgentConfigAdminRepository, user: CurrentUser) -> FastAPI:
    app = FastAPI()
    app.include_router(agent_config_router)
    app.dependency_overrides[get_agent_config] = lambda: repo
    app.dependency_overrides[get_audit] = lambda: _FakeAudit()
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture()
def admin_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="admin@test.com",
        name="Admin",
        role="admin",
    )


@pytest.mark.asyncio
async def test_create_agent_config_rejects_invalid_kinds(admin_user) -> None:
    repo = FakeAgentConfigAdminRepository()
    app = _build_app(repo, admin_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/agent-config/versions",
            json={
                "top_k": 6,
                "candidate_k": 25,
                "full_corpus_for_all_intents": False,
                "intents": [
                    {
                        "intent_slug": "dosage_question",
                        "display_label": "X",
                        "classifier_hint": "x",
                        "document_kinds": ["invalid_kind"],
                    }
                ],
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_config_success(admin_user) -> None:
    repo = FakeAgentConfigAdminRepository()
    app = _build_app(repo, admin_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/agent-config/versions",
            json={
                "top_k": 10,
                "candidate_k": 25,
                "full_corpus_for_all_intents": False,
                "intents": _default_intents(),
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["top_k"] == 10
    assert repo._versions[-1].top_k == 10
