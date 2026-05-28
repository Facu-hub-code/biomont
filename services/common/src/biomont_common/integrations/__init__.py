"""Integraciones externas encapsuladas (OpenAI/LangChain, etc.)."""

from biomont_common.integrations.openai_factory import (
    build_chat_model,
    build_embeddings,
)
from biomont_common.integrations.text_splitter import (
    MarkdownChunker,
    StructuredChunk,
    StructuredChunkerError,
    StructuredChunkingResult,
    StructuredMarkdownChunker,
    StructuredSection,
    TextChunk,
)

__all__ = [
    "MarkdownChunker",
    "StructuredChunk",
    "StructuredChunkerError",
    "StructuredChunkingResult",
    "StructuredMarkdownChunker",
    "StructuredSection",
    "TextChunk",
    "build_chat_model",
    "build_embeddings",
]
