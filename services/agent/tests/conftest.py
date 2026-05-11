"""Fixtures y fakes para el agente.

Cumple `.cursor/rules/testing-policy-python.mdc`: nada de OpenAI/Meta
reales en CI. Toda la infra esta abstraida detras de fakes.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence
from uuid import UUID

import pytest

# Setear variables minimas antes de cualquier import del codigo de app.
os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "000")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test-token")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "verify-test")
os.environ.setdefault("WHATSAPP_APP_SECRET", "app-secret-test")
os.environ.setdefault("AGENT_SIMILARITY_THRESHOLD", "0.75")
os.environ.setdefault("AGENT_TOP_K", "3")
os.environ.setdefault("LOG_JSON", "false")


# ---------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------
@dataclass(slots=True)
class FakeRtcUser:
    id: UUID
    phone_e164: str
    name: str
    enabled: bool
    countries: list[str]


class FakeRtcRepository:
    def __init__(self, users: dict[str, FakeRtcUser]) -> None:
        self._users = users

    async def find_by_phone(self, phone_e164: str):
        return self._users.get(phone_e164)


class FakeConversationRepository:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.tickets: list[dict[str, Any]] = []
        self.conversations: list[UUID] = []

    async def get_or_create_active_conversation(self, rtc_user_id: UUID, **_: Any) -> UUID:
        new_id = uuid.uuid4()
        self.conversations.append(new_id)
        return new_id

    async def insert_message(self, **kwargs: Any) -> UUID:
        new_id = uuid.uuid4()
        self.messages.append({"id": new_id, **kwargs})
        return new_id

    async def insert_decision(self, **kwargs: Any) -> UUID:
        new_id = uuid.uuid4()
        self.decisions.append({"id": new_id, **kwargs})
        return new_id

    async def insert_ticket(self, **kwargs: Any) -> UUID:
        new_id = uuid.uuid4()
        self.tickets.append({"id": new_id, **kwargs})
        return new_id


@dataclass(slots=True)
class FakeActivePrompt:
    version: int
    content: str


class FakeSystemPromptRepository:
    def __init__(self, prompt: FakeActivePrompt | None) -> None:
        self._prompt = prompt

    async def get_active(self) -> FakeActivePrompt | None:
        return self._prompt

    def invalidate(self) -> None:
        ...


class FakeWhatsAppClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_text(self, *, to_phone_e164: str, body: str) -> None:
        self.sent.append({"to": to_phone_e164, "body": body})


@dataclass(slots=True)
class FakeChunkHit:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    country_iso: str | None
    chunk_index: int
    content: str
    similarity: float
    metadata: dict = field(default_factory=dict)


class FakeRagRepository:
    def __init__(self, hits: Sequence[FakeChunkHit]) -> None:
        self._hits = list(hits)
        self.last_allowed_countries: list[str] | None = None

    async def search_similar_chunks(
        self,
        *,
        query_embedding: Sequence[float],
        allowed_countries: Iterable[str],
        top_k: int,
    ) -> list[FakeChunkHit]:
        self.last_allowed_countries = list(allowed_countries)
        return self._hits[:top_k]


class FakeEmbeddings:
    async def aembed_query(self, _query: str) -> list[float]:
        return [0.0] * 1536

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


@pytest.fixture()
def fake_rtc_user() -> FakeRtcUser:
    return FakeRtcUser(
        id=uuid.uuid4(),
        phone_e164="+51999000111",
        name="RTC Test",
        enabled=True,
        countries=["PE", "EC"],
    )


@pytest.fixture()
def fake_chunk_hits() -> list[FakeChunkHit]:
    doc_id = uuid.uuid4()
    return [
        FakeChunkHit(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_title="Ficha producto X",
            country_iso="PE",
            chunk_index=0,
            content="Dosis: 0.2 mg/kg subcutanea.",
            similarity=0.92,
        ),
        FakeChunkHit(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_title="Ficha producto X",
            country_iso="PE",
            chunk_index=1,
            content="Contraindicacion: animales gestantes.",
            similarity=0.81,
        ),
    ]
