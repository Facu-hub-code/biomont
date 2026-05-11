"""Healthcheck minimo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from biomont_common.db.pool import DatabasePool

from app.api.dependencies import get_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    pool: Annotated[DatabasePool, Depends(get_pool)],
) -> dict[str, str]:
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}
