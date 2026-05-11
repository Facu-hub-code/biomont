"""Entrypoint del agente WhatsApp."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from biomont_common.db.conversation_repository import ConversationRepository
from biomont_common.db.pool import create_pool
from biomont_common.db.rag_repository import RagRepository
from biomont_common.db.rtc_repository import RtcRepository
from biomont_common.db.system_prompt_repository import SystemPromptRepository
from biomont_common.integrations.openai_factory import (
    build_chat_model,
    build_embeddings,
)
from biomont_common.logging import configure_logging, get_logger

from app.agent.orchestrator import AgentOrchestrator
from app.agent.rag_pipeline import RagPipeline
from app.api.health_router import router as health_router
from app.api.whatsapp_router import router as whatsapp_router
from app.integrations.whatsapp_client import MetaWhatsAppClient
from app.settings import get_agent_settings

_SERVICE_NAME = "agent"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
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
    agent_settings = get_agent_settings()

    pool = create_pool()
    await pool.start()
    app.state.pool = pool

    whatsapp_client = MetaWhatsAppClient()
    app.state.whatsapp_client = whatsapp_client

    rag = RagRepository(pool)
    rtc_repo = RtcRepository(pool)
    conv_repo = ConversationRepository(pool)
    prompt_repo = SystemPromptRepository(
        pool,
        cache_ttl_seconds=agent_settings.system_prompt_cache_ttl_seconds,
    )

    embeddings = build_embeddings()
    chat_model = build_chat_model()

    pipeline = RagPipeline(
        rag=rag,
        embeddings=embeddings,
        chat_model=chat_model,
        top_k=agent_settings.top_k,
    )
    orchestrator = AgentOrchestrator(
        rtc_repository=rtc_repo,
        conversation_repository=conv_repo,
        system_prompt_repository=prompt_repo,
        pipeline=pipeline,
        whatsapp_client=whatsapp_client,
        similarity_threshold=agent_settings.similarity_threshold,
    )
    app.state.orchestrator = orchestrator
    logger.info("startup_complete", action="startup")
    try:
        yield
    finally:
        await whatsapp_client.close()
        await pool.stop()
        logger.info("shutdown_complete", action="shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Biomont Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(whatsapp_router)
    return app


app = create_app()
