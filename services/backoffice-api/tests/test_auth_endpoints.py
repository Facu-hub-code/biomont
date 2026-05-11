"""Tests HTTP del flujo de auth (login + me) con repos fake."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.auth_router import router as auth_router
from app.api.dependencies import get_bo_users
from app.db.bo_user_repository import BoUserRow
from app.services.security import hash_password


class FakeBoUserRepository:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.users = {
            "admin@example.com": BoUserRow(
                id=self.id,
                email="admin@example.com",
                password_hash=hash_password("biomont-admin"),
                name="Admin",
                role="admin",
                is_active=True,
            )
        }

    async def find_by_email(self, email: str):
        return self.users.get(email)

    async def find_by_id(self, user_id: uuid.UUID):
        for user in self.users.values():
            if user.id == user_id:
                return user
        return None


def _build_app(repo: FakeBoUserRepository) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_bo_users] = lambda: repo
    return app


@pytest.mark.asyncio
async def test_login_success_returns_token() -> None:
    repo = FakeBoUserRepository()
    app = _build_app(repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "biomont-admin"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401() -> None:
    repo = FakeBoUserRepository()
    app = _build_app(repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user() -> None:
    repo = FakeBoUserRepository()
    app = _build_app(repo)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "biomont-admin"},
        )
        token = login.json()["access_token"]
        me = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"
