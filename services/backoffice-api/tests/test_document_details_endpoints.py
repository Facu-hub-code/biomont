from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user, get_documents
from app.api.documents_router import router as documents_router
from app.schemas.auth import CurrentUser


@dataclass(slots=True)
class FakeDocument:
    id: uuid.UUID
    title: str
    product_name: str | None
    country_iso: str | None
    language: str
    status: str
    source_filename: str | None
    content_sha256: str | None
    markdown: str | None
    classification: dict
    uploaded_by: uuid.UUID | None
    validated_by: uuid.UUID | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    kind: str
    product_id: uuid.UUID | None
    chunk_count: int


@dataclass(slots=True)
class FakeSection:
    id: uuid.UUID
    document_id: uuid.UUID
    section_index: int
    parent_section_id: uuid.UUID | None
    section_number: str | None
    section_title: str | None
    section_kind: str | None
    page_start: int | None
    page_end: int | None
    raw_text: str | None
    created_at: datetime


class FakeDocumentRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.document_id = uuid.uuid4()
        self.document = FakeDocument(
            id=self.document_id,
            title="Doc",
            product_name="Prod",
            country_iso="PE",
            language="es",
            status="validated",
            source_filename=None,
            content_sha256=None,
            markdown="contenido",
            classification={},
            uploaded_by=None,
            validated_by=None,
            validated_at=None,
            created_at=now,
            updated_at=now,
            kind="bitacora",
            product_id=None,
            chunk_count=1,
        )
        self.section = FakeSection(
            id=uuid.uuid4(),
            document_id=self.document_id,
            section_index=1,
            parent_section_id=None,
            section_number="1",
            section_title="Intro",
            section_kind="header",
            page_start=1,
            page_end=1,
            raw_text="texto",
            created_at=now,
        )

    async def list_documents(self):
        return [self.document]

    async def get_document(self, document_id: uuid.UUID):
        if document_id != self.document_id:
            return None
        return self.document

    async def list_document_sections(self, document_id: uuid.UUID, *, page: int, page_size: int):
        _ = (page, page_size)
        if document_id != self.document_id:
            return 0, []
        return 1, [self.section]

    async def list_document_knowledge_chunks(self, document_id: uuid.UUID, *, page: int, page_size: int):
        _ = (page, page_size)
        if document_id != self.document_id:
            return 0, []
        return 0, []

    async def list_document_legacy_chunks(self, document_id: uuid.UUID, *, page: int, page_size: int):
        _ = (page, page_size)
        if document_id != self.document_id:
            return 0, []
        return 0, []

    async def list_document_faq_entries(self, document_id: uuid.UUID, *, page: int, page_size: int):
        _ = (page, page_size)
        if document_id != self.document_id:
            return 0, []
        return 0, []


def _build_app(repo: FakeDocumentRepository, user: CurrentUser | None) -> FastAPI:
    app = FastAPI()
    app.include_router(documents_router)
    app.dependency_overrides[get_documents] = lambda: repo

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
async def test_list_document_sections_happy_path(viewer_user) -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/documents/{repo.document_id}/sections")
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_document_sections_404(viewer_user) -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/documents/{uuid.uuid4()}/sections")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_document_knowledge_chunks_401() -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/documents/{repo.document_id}/knowledge-chunks")
    assert response.status_code == 401
