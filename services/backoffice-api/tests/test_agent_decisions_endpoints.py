from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.agent_decisions_router import router as agent_decisions_router
from app.api.dependencies import (
    get_agent_decision_enrichment,
    get_agent_decisions,
    get_current_user,
)
from app.schemas.agent_decisions import (
    AgentDecisionDetailEnrichment,
    GraphTraceStepDisplay,
    RetrievedItemEnriched,
)
from app.schemas.auth import CurrentUser
from app.services.agent_decision_enrichment import AgentDecisionEnrichmentService


@dataclass(slots=True)
class FakeDecisionListRow:
    id: uuid.UUID
    message_id: uuid.UUID | None
    decision: str
    reasoning: str | None
    top_similarity: float | None
    system_prompt_version: int | None
    created_at: datetime
    conversation_id: uuid.UUID | None
    rtc_user_id: uuid.UUID | None
    rtc_name: str | None
    phone_e164: str | None
    message_preview: str | None


@dataclass(slots=True)
class FakeDecisionDetailRow:
    id: uuid.UUID
    message_id: uuid.UUID | None
    decision: str
    reasoning: str | None
    retrieved: list[dict]
    top_similarity: float | None
    system_prompt_version: int | None
    graph_trace: list[dict]
    created_at: datetime
    message_content: str | None
    message_role: str | None
    conversation_id: uuid.UUID | None
    conversation_started_at: datetime | None
    rtc_user_id: uuid.UUID | None
    rtc_name: str | None
    phone_e164: str | None
    previous_user_message: str | None


class FakeAgentDecisionRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.decision_id = uuid.uuid4()
        self.list_row = FakeDecisionListRow(
            id=self.decision_id,
            message_id=uuid.uuid4(),
            decision="answered",
            reasoning="ok",
            top_similarity=0.95,
            system_prompt_version=2,
            created_at=now,
            conversation_id=uuid.uuid4(),
            rtc_user_id=uuid.uuid4(),
            rtc_name="RTC Uno",
            phone_e164="+51999000111",
            message_preview="respuesta",
        )
        self.detail_row = FakeDecisionDetailRow(
            id=self.decision_id,
            message_id=self.list_row.message_id,
            decision="answered",
            reasoning="ok",
            retrieved=[{"document_id": "x", "chunk_id": "y", "similarity": 0.9}],
            top_similarity=0.95,
            system_prompt_version=2,
            graph_trace=[{"node": "answerer", "latency_ms": 20}],
            created_at=now,
            message_content="respuesta",
            message_role="assistant",
            conversation_id=self.list_row.conversation_id,
            conversation_started_at=now,
            rtc_user_id=self.list_row.rtc_user_id,
            rtc_name="RTC Uno",
            phone_e164="+51999000111",
            previous_user_message="consulta",
        )

    async def list_decisions(self, **_kwargs):
        return 1, [self.list_row]

    async def get_decision(self, decision_id: uuid.UUID):
        if decision_id != self.decision_id:
            return None
        return self.detail_row


class FakeEnrichmentService(AgentDecisionEnrichmentService):
    def __init__(self) -> None:
        pass

    async def enrich(self, *, decision_id, retrieved, graph_trace):
        return AgentDecisionDetailEnrichment(
            retrieved_items=[
                RetrievedItemEnriched(
                    document_id=uuid.uuid4(),
                    chunk_id=uuid.uuid4(),
                    similarity=0.9,
                    document_title="Doc enriquecido",
                    chunk_label="ficha · INDICACIONES",
                    chunk_content="contenido",
                    chunk_found=True,
                )
            ],
            graph_trace_display=[
                GraphTraceStepDisplay(
                    node="answerer",
                    outcome="ok",
                    latency_ms=20.0,
                    display={"intent": "clinical_protocol"},
                    payload_raw={"intent": "clinical_protocol"},
                )
            ],
        )


def _build_app(repo: FakeAgentDecisionRepository, user: CurrentUser | None) -> FastAPI:
    app = FastAPI()
    app.include_router(agent_decisions_router)
    app.dependency_overrides[get_agent_decisions] = lambda: repo
    app.dependency_overrides[get_agent_decision_enrichment] = lambda: FakeEnrichmentService()

    def _current_user():
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user

    app.dependency_overrides[get_current_user] = _current_user
    return app


@pytest.fixture()
def viewer_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="viewer@x.com",
        name="viewer",
        role="viewer",
    )


@pytest.mark.asyncio
async def test_list_agent_decisions_happy_path(viewer_user) -> None:
    repo = FakeAgentDecisionRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/agent-decisions?decision=answered&page=1&page_size=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["decision"] == "answered"


@pytest.mark.asyncio
async def test_list_agent_decisions_401_without_auth() -> None:
    repo = FakeAgentDecisionRepository()
    app = _build_app(repo, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/agent-decisions")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_agent_decision_includes_enrichment(viewer_user) -> None:
    repo = FakeAgentDecisionRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/agent-decisions/{repo.decision_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["enrichment"]["retrieved_items"][0]["document_title"] == "Doc enriquecido"
    assert body["enrichment"]["graph_trace_display"][0]["node"] == "answerer"


@pytest.mark.asyncio
async def test_get_agent_decision_404_when_missing(viewer_user) -> None:
    repo = FakeAgentDecisionRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/agent-decisions/{uuid.uuid4()}")
    assert response.status_code == 404
