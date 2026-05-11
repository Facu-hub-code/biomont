"""Factories para los clientes LangChain de OpenAI.

Sigue `.cursor/rules/dependency-constraints.mdc`: no se construyen clientes
globales en import-time; cada servicio inyecta la instancia que necesita.
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from biomont_common.settings import OpenAISettings, get_openai_settings


def build_chat_model(
    settings: OpenAISettings | None = None,
    *,
    temperature: float = 0.1,
    timeout: float | None = None,
) -> ChatOpenAI:
    """Construye un `ChatOpenAI` reusable para el agente."""

    cfg = settings or get_openai_settings()
    return ChatOpenAI(
        model=cfg.chat_model,
        api_key=cfg.api_key.get_secret_value(),
        temperature=temperature,
        timeout=timeout or cfg.request_timeout_s,
    )


def build_embeddings(
    settings: OpenAISettings | None = None,
) -> OpenAIEmbeddings:
    """Construye un `OpenAIEmbeddings` con la dim del modelo configurado."""

    cfg = settings or get_openai_settings()
    return OpenAIEmbeddings(
        model=cfg.embeddings_model,
        api_key=cfg.api_key.get_secret_value(),
        dimensions=cfg.embeddings_dim,
        timeout=cfg.request_timeout_s,
    )
