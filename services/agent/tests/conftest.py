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

from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit
from biomont_common.schemas.products import ProductCandidate

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

    async def find_by_id(self, rtc_user_id: UUID):
        for u in self._users.values():
            if u.id == rtc_user_id:
                return u
        return None


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


class FakeAgentConfigRepository:
    """Devuelve snapshot env para tests del grafo sin Postgres."""

    def __init__(self, config=None) -> None:
        from biomont_common.db.agent_config_repository import (
            snapshot_from_rag_settings,
        )
        from biomont_common.settings import get_rag_settings

        self._config = config or snapshot_from_rag_settings(get_rag_settings())

    async def get_active(self, *, rag_fallback=None):
        return self._config

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


# ----------------------------------------------------------------------
# Fakes spec 003 (grafo)
# ----------------------------------------------------------------------


class FakeProductRepository:
    """Fake controlado para el ProductResolver."""

    def __init__(
        self,
        candidates: Sequence[ProductCandidate] | None = None,
        by_id: dict[UUID, Any] | None = None,
    ) -> None:
        self.candidates = list(candidates or [])
        self.by_id = dict(by_id or {})
        self.last_query: str | None = None

    async def search_candidates(
        self,
        query_text: str,
        *,
        allowed_countries=None,
        limit: int = 5,
    ) -> list[ProductCandidate]:
        self.last_query = query_text
        return list(self.candidates[:limit])

    async def get_by_id(self, product_id: UUID):
        return self.by_id.get(product_id)

class FakeHybridRagRepository:
    def __init__(self, hits: Sequence[HybridChunkHit] | None = None) -> None:
        self._hits = list(hits or [])
        self.last_call: dict[str, Any] | None = None

    async def search_hybrid_chunks(self, **kwargs: Any) -> list[HybridChunkHit]:
        self.last_call = dict(kwargs)
        return list(self._hits)


class FakeConversationStateRepository:
    def __init__(self) -> None:
        self.state_by_conv: dict[UUID, dict[str, Any]] = {}

    async def get(self, conversation_id: UUID):
        return self.state_by_conv.get(conversation_id)

    async def upsert(self, **kwargs: Any) -> None:
        conv = kwargs["conversation_id"]
        self.state_by_conv[conv] = kwargs


@pytest.fixture()
def fake_hybrid_chunks() -> list[HybridChunkHit]:
    doc_id = uuid.uuid4()
    return [
        HybridChunkHit(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_title="Bitacora Proteggo 3M",
            product_id=None,
            kind=DocumentKind.bitacora,
            chunk_index=0,
            section_type="protocol",
            content="Para DAPP usar Proteggo 3M segun protocolo.",
            country_iso="PE",
            vector_score=0.9,
            bm25_score=0.8,
            final_score=0.88,
        ),
    ]


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
