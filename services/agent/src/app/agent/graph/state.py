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

    classifier_system_prompt: str
    classifier_cache_namespace: str
    runtime_full_corpus: bool
    intent_kinds_by_slug: dict[str, list[str] | None]
    retrieval_top_k: int
    retrieval_candidate_k: int


def initial_state(
    *,
    query: str,
    allowed_countries: list[str],
    system_prompt: str,
    conversation_id: UUID | None,
    inherited_product_id: UUID | None = None,
    classifier_system_prompt: str = "",
    classifier_cache_namespace: str = "default",
    runtime_full_corpus: bool = False,
    intent_kinds_by_slug: dict[str, list[str] | None] | None = None,
    retrieval_top_k: int = 6,
    retrieval_candidate_k: int = 25,
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
        classifier_system_prompt=classifier_system_prompt,
        classifier_cache_namespace=classifier_cache_namespace,
        runtime_full_corpus=runtime_full_corpus,
        intent_kinds_by_slug=intent_kinds_by_slug or {},
        retrieval_top_k=retrieval_top_k,
        retrieval_candidate_k=retrieval_candidate_k,
    )
