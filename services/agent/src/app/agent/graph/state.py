"""Estado compartido entre nodos del grafo (spec 003)."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict
from uuid import UUID

from biomont_common.schemas.agent_graph import GraphNodeTrace, Intent
from biomont_common.schemas.knowledge import DocumentKind, HybridChunkHit
from biomont_common.schemas.products import ProductCandidate


class AgentGraphState(TypedDict, total=False):
    """Estado del grafo del agente."""

    query: str
    allowed_countries: list[str]
    system_prompt: str
    conversation_id: UUID | None
    inherited_product_id: UUID | None

    intent: Intent
    intent_confidence: float

    product_id: UUID | None
    product_name: str | None
    product_inherited: bool
    ambiguous_candidates: list[ProductCandidate]

    filter_kinds: list[DocumentKind] | None

    retrieved: list[HybridChunkHit]
    top_similarity: float

    answer_text: str | None
    citations: list[dict[str, Any]]
    error: str | None

    state_updated: bool

    trace: Annotated[list[GraphNodeTrace], add]


def initial_state(
    *,
    query: str,
    allowed_countries: list[str],
    system_prompt: str,
    conversation_id: UUID | None,
    inherited_product_id: UUID | None = None,
) -> AgentGraphState:
    return AgentGraphState(
        query=query,
        allowed_countries=allowed_countries,
        system_prompt=system_prompt,
        conversation_id=conversation_id,
        inherited_product_id=inherited_product_id,
        ambiguous_candidates=[],
        retrieved=[],
        citations=[],
        top_similarity=0.0,
        trace=[],
        state_updated=False,
        product_inherited=False,
    )
