from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_audit, get_current_user, get_documents
from app.api.documents_router import router as documents_router
from app.db.audit_repository import dumps_audit_payload
from app.schemas.auth import CurrentUser


@dataclass(slots=True)
class FakeDocumentRow:
    id: uuid.UUID
    title: str
    product_name: str | None
    country_iso: str | None
    language: str
    status: str
    source_filename: str | None
    content_sha256: str | None
    markdown: str | None
    classification: dict[str, Any]
    uploaded_by: uuid.UUID | None
    validated_by: uuid.UUID | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    kind: str
    product_id: uuid.UUID | None
    linked_products: list | None
    chunk_count: int


class FakeAuditRepository:
    async def record(
        self,
        *,
        before: dict | None = None,
        after: dict | None = None,
        **_kwargs,
    ) -> None:
        if before is not None:
            dumps_audit_payload(before)
        if after is not None:
            dumps_audit_payload(after)


class FakeDocumentRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.document_id = uuid.uuid4()
        self.documents: dict[uuid.UUID, FakeDocumentRow] = {
            self.document_id: FakeDocumentRow(
                id=self.document_id,
                title="Ficha tecnica",
                product_name="Proteggo",
                country_iso="PE",
                language="es",
                status="validated",
                source_filename="ficha.pdf",
                content_sha256="abc",
                markdown="# doc",
                classification={},
                uploaded_by=None,
                validated_by=None,
                validated_at=None,
                created_at=now,
                updated_at=now,
                kind="ficha_tecnica",
                product_id=None,
                linked_products=[],
                chunk_count=12,
            )
        }

    async def list_documents(self) -> list[FakeDocumentRow]:
        return list(self.documents.values())

    async def get_document(self, document_id: uuid.UUID) -> FakeDocumentRow | None:
        return self.documents.get(document_id)

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        return self.documents.pop(document_id, None) is not None


def _build_app(repo: FakeDocumentRepository, user: CurrentUser | None) -> FastAPI:
    app = FastAPI()
    app.include_router(documents_router)
    app.dependency_overrides[get_documents] = lambda: repo
    app.dependency_overrides[get_audit] = lambda: FakeAuditRepository()

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


@pytest.fixture()
def scientist_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="scientist@x.com",
        name="scientist",
        role="scientist",
    )


@pytest.mark.asyncio
async def test_delete_document_returns_204(scientist_user) -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, scientist_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/documents/{repo.document_id}")
    assert response.status_code == 204
    assert repo.document_id not in repo.documents


@pytest.mark.asyncio
async def test_delete_document_403_for_viewer(viewer_user) -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/documents/{repo.document_id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_document_404_when_missing(scientist_user) -> None:
    repo = FakeDocumentRepository()
    app = _build_app(repo, scientist_user)
    missing = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/documents/{missing}")
    assert response.status_code == 404
