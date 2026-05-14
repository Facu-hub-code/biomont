from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_audit, get_current_user, get_products
from app.api.products_router import router as products_router
from app.schemas.auth import CurrentUser


@dataclass(slots=True)
class FakeProductRow:
    id: uuid.UUID
    name: str
    brand: str
    duration_type: str | None
    description: str | None
    country_iso: str | None
    created_at: datetime
    updated_at: datetime
    alias_count: int
    document_count: int


@dataclass(slots=True)
class FakeAliasRow:
    id: uuid.UUID
    product_id: uuid.UUID
    alias: str
    normalized_alias: str
    source: str
    confidence: float
    created_at: datetime


class FakeAuditRepository:
    async def record(self, **_kwargs) -> None:
        return None


class FakeProductRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.product_id = uuid.uuid4()
        self.alias_id = uuid.uuid4()
        self.products: dict[uuid.UUID, FakeProductRow] = {
            self.product_id: FakeProductRow(
                id=self.product_id,
                name="Boviforte",
                brand="Biomont",
                duration_type="mensual",
                description="desc",
                country_iso="PE",
                created_at=now,
                updated_at=now,
                alias_count=1,
                document_count=0,
            )
        }
        self.aliases: dict[tuple[uuid.UUID, uuid.UUID], FakeAliasRow] = {
            (self.product_id, self.alias_id): FakeAliasRow(
                id=self.alias_id,
                product_id=self.product_id,
                alias="bovi forte",
                normalized_alias="bovi forte",
                source="manual",
                confidence=1.0,
                created_at=now,
            )
        }
        self.raise_conflict = False
        self.delete_conflict = False

    async def list_products(self, *, page: int, page_size: int) -> tuple[int, list[Any]]:
        _ = (page, page_size)
        rows = list(self.products.values())
        return len(rows), rows

    async def get_product(self, product_id: uuid.UUID):
        return self.products.get(product_id)

    async def create_product(self, **kwargs) -> uuid.UUID:
        if self.raise_conflict:
            import asyncpg

            raise asyncpg.UniqueViolationError("duplicate")
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        self.products[new_id] = FakeProductRow(
            id=new_id,
            name=kwargs["name"],
            brand=kwargs["brand"],
            duration_type=kwargs.get("duration_type"),
            description=kwargs.get("description"),
            country_iso=kwargs.get("country_iso"),
            created_at=now,
            updated_at=now,
            alias_count=0,
            document_count=0,
        )
        return new_id

    async def update_product(self, product_id: uuid.UUID, **kwargs):
        if self.raise_conflict:
            import asyncpg

            raise asyncpg.UniqueViolationError("duplicate")
        row = self.products.get(product_id)
        if row is None:
            return None
        data = asdict(row)
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        updated = FakeProductRow(**data)
        self.products[product_id] = updated
        return updated

    async def delete_product(self, product_id: uuid.UUID) -> bool:
        if self.delete_conflict:
            import asyncpg

            raise asyncpg.ForeignKeyViolationError("fk")
        return self.products.pop(product_id, None) is not None

    async def list_aliases(
        self,
        product_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[int, list[Any]]:
        _ = (page, page_size)
        rows = [v for (pid, _), v in self.aliases.items() if pid == product_id]
        return len(rows), rows

    async def get_alias(self, product_id: uuid.UUID, alias_id: uuid.UUID):
        return self.aliases.get((product_id, alias_id))

    async def create_alias(self, *, product_id: uuid.UUID, **kwargs) -> uuid.UUID:
        if self.raise_conflict:
            import asyncpg

            raise asyncpg.UniqueViolationError("duplicate alias")
        alias_id = uuid.uuid4()
        row = FakeAliasRow(
            id=alias_id,
            product_id=product_id,
            alias=kwargs["alias"],
            normalized_alias=kwargs["alias"].lower(),
            source=kwargs.get("source", "manual"),
            confidence=float(kwargs.get("confidence", 1.0)),
            created_at=datetime.now(timezone.utc),
        )
        self.aliases[(product_id, alias_id)] = row
        return alias_id

    async def update_alias(self, *, product_id: uuid.UUID, alias_id: uuid.UUID, **kwargs):
        if self.raise_conflict:
            import asyncpg

            raise asyncpg.UniqueViolationError("duplicate alias")
        existing = self.aliases.get((product_id, alias_id))
        if existing is None:
            return None
        updated = FakeAliasRow(
            id=existing.id,
            product_id=existing.product_id,
            alias=kwargs.get("alias") or existing.alias,
            normalized_alias=(kwargs.get("alias") or existing.alias).lower(),
            source=kwargs.get("source") or existing.source,
            confidence=float(
                kwargs.get("confidence")
                if kwargs.get("confidence") is not None
                else existing.confidence
            ),
            created_at=existing.created_at,
        )
        self.aliases[(product_id, alias_id)] = updated
        return updated

    async def delete_alias(self, *, product_id: uuid.UUID, alias_id: uuid.UUID) -> bool:
        return self.aliases.pop((product_id, alias_id), None) is not None


def _build_app(repo: FakeProductRepository, user: CurrentUser | None) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router)
    app.dependency_overrides[get_products] = lambda: repo
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


@pytest.fixture()
def admin_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="admin@x.com",
        name="admin",
        role="admin",
    )


@pytest.mark.asyncio
async def test_list_products_happy_path(viewer_user) -> None:
    repo = FakeProductRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/products")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Boviforte"


@pytest.mark.asyncio
async def test_list_products_401_when_unauthenticated() -> None:
    repo = FakeProductRepository()
    app = _build_app(repo, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/products")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_product_403_for_viewer(viewer_user) -> None:
    repo = FakeProductRepository()
    app = _build_app(repo, viewer_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/products",
            json={"name": "Nuevo", "brand": "Biomont"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_product_409_when_conflict(scientist_user) -> None:
    repo = FakeProductRepository()
    repo.raise_conflict = True
    app = _build_app(repo, scientist_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/products",
            json={"name": "Duplicado", "brand": "Biomont"},
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_product_403_for_scientist(scientist_user) -> None:
    repo = FakeProductRepository()
    app = _build_app(repo, scientist_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/products/{repo.product_id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_product_409_on_fk_conflict(admin_user) -> None:
    repo = FakeProductRepository()
    repo.delete_conflict = True
    app = _build_app(repo, admin_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/products/{repo.product_id}")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_alias_409_when_conflict(scientist_user) -> None:
    repo = FakeProductRepository()
    repo.raise_conflict = True
    app = _build_app(repo, scientist_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/products/{repo.product_id}/aliases",
            json={"alias": "bovi forte"},
        )
    assert response.status_code == 409
