"""Integraciones externas encapsuladas (OpenAI/LangChain, etc.)."""

from biomont_common.integrations.faq_extractor import (
    FaqExtractor,
    FaqExtractorError,
    FaqExtractorProtocol,
    FaqList,
    FaqPair,
)
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
    "FaqExtractor",
    "FaqExtractorError",
    "FaqExtractorProtocol",
    "FaqList",
    "FaqPair",
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
