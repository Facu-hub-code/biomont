"""Integraciones externas encapsuladas (OpenAI/LangChain, etc.)."""

from biomont_common.integrations.openai_factory import (
    build_chat_model,
    build_embeddings,
)

__all__ = ["build_chat_model", "build_embeddings"]
