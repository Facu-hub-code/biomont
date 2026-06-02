"""Entrypoint del backoffice-api."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from biomont_common.db.pool import DatabasePool, create_pool
from biomont_common.logging import configure_logging, get_logger

from app.api.comparison_router import router as comparison_router
from app.api.dosing_router import router as dosing_router
from app.api.agent_config_router import router as agent_config_router
from app.api.analytics_router import router as analytics_router
from app.api.agent_decisions_router import router as agent_decisions_router
from app.api.auth_router import router as auth_router
from app.api.conversations_router import router as conversations_router
from app.api.documents_router import router as documents_router
from app.api.health_router import router as health_router
from app.api.playground_bo_router import router as playground_bo_router
from app.api.products_router import router as products_router
from app.api.rtcs_router import router as rtcs_router
from app.api.system_prompt_router import router as system_prompt_router
from app.api.tickets_router import router as tickets_router
from app.settings import get_backoffice_settings

_SERVICE_NAME = "backoffice-api"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers["x-request-id"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(_SERVICE_NAME)
    logger = get_logger("startup")
    pool = create_pool()
    await pool.start()
    app.state.pool = pool
    logger.info("startup_complete", action="startup")
    try:
        yield
    finally:
        await pool.stop()
        logger.info("shutdown_complete", action="shutdown")


def create_app() -> FastAPI:
    settings = get_backoffice_settings()
    app = FastAPI(
        title="Biomont Backoffice API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(rtcs_router)
    app.include_router(conversations_router)
    app.include_router(playground_bo_router)
    app.include_router(system_prompt_router)
    app.include_router(agent_config_router)
    app.include_router(tickets_router)
    app.include_router(analytics_router)
    app.include_router(products_router)
    app.include_router(dosing_router)
    app.include_router(comparison_router)
    app.include_router(agent_decisions_router)
    return app


app = create_app()
