"""Schemas pydantic compartidos entre servicios."""

from biomont_common.schemas.agent_graph import (
    ConversationStateRecord,
    GraphNodeTrace,
    Intent,
    IntentClassification,
)
from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit
from biomont_common.schemas.products import (
    Product,
    ProductAlias,
    ProductCandidate,
)
from biomont_common.schemas.rag import Citation, RagAnswer, RetrievedChunk

__all__ = [
    "Citation",
    "ConversationStateRecord",
    "DocumentKind",
    "GraphNodeTrace",
    "HybridChunkHit",
    "Intent",
    "IntentClassification",
    "Product",
    "ProductAlias",
    "ProductCandidate",
    "RagAnswer",
    "RetrievedChunk",
]
