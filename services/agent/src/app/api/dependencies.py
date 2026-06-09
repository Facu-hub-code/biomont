"""Factories de dependencias para los routers del agente."""

from __future__ import annotations

from fastapi import Request

from biomont_common.db.whatsapp_inbound_repository import WhatsappInboundRepository

from app.agent.orchestrator import AgentOrchestrator


def get_orchestrator(request: Request) -> AgentOrchestrator:
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    return orchestrator


def get_whatsapp_inbound_repository(request: Request) -> WhatsappInboundRepository:
    repo: WhatsappInboundRepository = request.app.state.inbound_repository
    return repo
