"""Tests de vinculos producto-documento (spec 006)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_audit,
    get_current_user,
    get_document_products,
    get_documents,
    get_products,
)
from app.api.documents_router import router as documents_router
from app.api.products_router import router as products_router
from app.schemas.auth import CurrentUser


@dataclass(slots=True)
class FakeLinkedDoc:
    document_id: uuid.UUID
    title: str
    kind: str
    status: str
    country_iso: str | None
    is_primary: bool
    updated_at: datetime


@dataclass(slots=True)
class FakeLinkedProduct:
    product_id: uuid.UUID
    name: str
    brand: str
    is_primary: bool


class FakeAuditRepository:
    async def record(self, **_kwargs) -> None:
        return None


class FakeProductAdminRepository:
    def __init__(self) -> None:
        self.product_id = uuid.uuid4()

    async def get_product(self, product_id: uuid.UUID):
        if product_id == self.product_id:
            return object()
        return None


class FakeDocumentRepository:
    def __init__(self, document_id: uuid.UUID) -> None:
        self.document_id = document_id

    async def get_document(self, document_id: uuid.UUID):
        if document_id == self.document_id:
            return object()
        return None


class FakeDocumentProductRepository:
    def __init__(self) -> None:
        self.product_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.known_products: set[uuid.UUID] = {self.product_id}
        self.links: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.products_for_doc: list[FakeLinkedProduct] = []
        self.docs_for_product: list[FakeLinkedDoc] = []

    async def list_documents_for_product(self, product_id, *, page, page_size):
        _ = (product_id, page, page_size)
        return len(self.docs_for_product), self.docs_for_product

    async def list_products_for_document(self, document_id):
        _ = document_id
        return self.products_for_doc

    async def link(self, **kwargs) -> None:
        key = (kwargs["product_id"], kwargs["document_id"])
        if key in self.links:
            import asyncpg

            raise asyncpg.UniqueViolationError("dup")
        self.links.add(key)

    async def unlink(self, *, product_id, document_id) -> bool:
        key = (product_id, document_id)
        if key not in self.links:
            return False
        self.links.remove(key)
        return True

    async def replace_for_document(self, **kwargs) -> None:
        document_id = kwargs["document_id"]
        self.links = {k for k in self.links if k[1] != document_id}
        for pid in kwargs["product_ids"]:
            self.links.add((pid, document_id))

    async def document_exists(self, document_id: uuid.UUID) -> bool:
        return document_id == self.document_id

    async def product_exists(self, product_id: uuid.UUID) -> bool:
        return product_id in self.known_products

    async def link_exists(self, *, product_id, document_id) -> bool:
        return (product_id, document_id) in self.links


def _build_app(
    products: FakeProductAdminRepository,
    links: FakeDocumentProductRepository,
    documents: FakeDocumentRepository | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router)
    app.include_router(documents_router)
    user = CurrentUser(
        id=uuid.uuid4(),
        email="sci@test.com",
        name="Sci",
        role="scientist",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_products] = lambda: products
    app.dependency_overrides[get_document_products] = lambda: links
    app.dependency_overrides[get_audit] = lambda: FakeAuditRepository()
    if documents is not None:
        app.dependency_overrides[get_documents] = lambda: documents
    return app


@pytest.mark.asyncio
async def test_link_product_document_201() -> None:
    products = FakeProductAdminRepository()
    links = FakeDocumentProductRepository()
    links.product_id = products.product_id
    app = _build_app(products, links)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/products/{products.product_id}/documents",
            json={"document_id": str(links.document_id), "is_primary": True},
        )

    assert response.status_code == 201
    assert (products.product_id, links.document_id) in links.links


@pytest.mark.asyncio
async def test_link_duplicate_409() -> None:
    products = FakeProductAdminRepository()
    links = FakeDocumentProductRepository()
    links.product_id = products.product_id
    links.links.add((products.product_id, links.document_id))
    app = _build_app(products, links)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/products/{products.product_id}/documents",
            json={"document_id": str(links.document_id)},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_replace_document_products() -> None:
    products = FakeProductAdminRepository()
    links = FakeDocumentProductRepository()
    links.known_products.add(products.product_id)
    second_product = uuid.uuid4()
    links.known_products.add(second_product)
    links.products_for_doc = [
        FakeLinkedProduct(
            product_id=products.product_id,
            name="Proteggo M",
            brand="Biomont",
            is_primary=True,
        ),
        FakeLinkedProduct(
            product_id=second_product,
            name="Proteggo 3M",
            brand="Biomont",
            is_primary=False,
        ),
    ]
    docs = FakeDocumentRepository(links.document_id)
    app = _build_app(products, links, documents=docs)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/documents/{links.document_id}/products",
            json={
                "product_ids": [str(products.product_id), str(second_product)],
                "primary_product_id": str(second_product),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
