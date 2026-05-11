"""Factories de dependencias para los routers del agente."""

from __future__ import annotations

from fastapi import Request

from app.agent.orchestrator import AgentOrchestrator


def get_orchestrator(request: Request) -> AgentOrchestrator:
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    return orchestrator
