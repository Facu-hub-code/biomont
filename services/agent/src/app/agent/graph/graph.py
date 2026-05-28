"""Composicion del grafo LangGraph del agente (spec 003, simplificado en 007).

    IntentClassifier
        |
        v
    ProductResolver --(ambiguous)--> END (con mensaje de aclaracion)
        |
        v
    MetaFilter --> HybridRetriever --> Answerer --> StateUpdater --> END
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from biomont_common.db.agent_config_repository import AgentConfigRepository
from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import RagRepository
from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import GraphNodeTrace, Intent
from biomont_common.schemas.knowledge import HybridChunkHit
from biomont_common.schemas.products import ProductCandidate
from biomont_common.settings import RagSettings, get_rag_settings

from app.agent.graph.nodes import (
    AnswererNode,
    HybridRetrieverNode,
    IntentClassifierNode,
    MetaFilterNode,
    ProductResolverNode,
    StateUpdaterNode,
)
from app.agent.graph.state import AgentGraphState, initial_state

_logger = get_logger("agent.graph")


@dataclass(slots=True)
class GraphOutput:
    """Salida del grafo consumida por el orchestrator."""

    retrieved: list[HybridChunkHit]
    top_similarity: float
    answer_text: str | None
    citations: list[dict[str, Any]]
    intent: Intent | None
    product_id: UUID | None
    product_name: str | None
    product_inherited: bool
    ambiguous_candidates: list[ProductCandidate]
    graph_trace: list[GraphNodeTrace]
    error: str | None = None


def build_graph(
    *,
    rag_repository: RagRepository,
    product_repository: ProductRepository,
    state_repository: ConversationStateRepository,
    agent_config_repository: AgentConfigRepository,
    embeddings: Embeddings,
    chat_model: BaseChatModel,
    settings: RagSettings | None = None,
) -> "GraphPipeline":
    """Compila el grafo con los nodos parametrizados."""

    cfg = settings or get_rag_settings()

    nodes = {
        "IntentClassifier": IntentClassifierNode(chat_model=chat_model),
        "ProductResolver": ProductResolverNode(
            repository=product_repository,
            threshold=cfg.product_resolver_threshold,
            margin=cfg.product_resolver_margin,
        ),
        "MetaFilter": MetaFilterNode(
            full_corpus_for_all_intents=cfg.full_corpus_for_all_intents,
        ),
        "HybridRetriever": HybridRetrieverNode(
            repository=rag_repository,
            embeddings=embeddings,
            vector_weight=cfg.vector_weight,
            bm25_weight=cfg.bm25_weight,
            top_k=cfg.top_k,
            candidate_k=cfg.candidate_k,
        ),
        "Answerer": AnswererNode(chat_model=chat_model),
        "StateUpdater": StateUpdaterNode(repository=state_repository),
    }

    graph: StateGraph = StateGraph(AgentGraphState)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "IntentClassifier")
    graph.add_edge("IntentClassifier", "ProductResolver")

    graph.add_conditional_edges(
        "ProductResolver",
        _route_after_resolver,
        {
            "ambiguous": END,
            "ok": "MetaFilter",
        },
    )

    graph.add_edge("MetaFilter", "HybridRetriever")
    graph.add_edge("HybridRetriever", "Answerer")
    graph.add_edge("Answerer", "StateUpdater")
    graph.add_edge("StateUpdater", END)

    compiled = graph.compile()
    return GraphPipeline(
        compiled=compiled,
        agent_config_repository=agent_config_repository,
        rag_settings=cfg,
    )


def _route_after_resolver(state: dict) -> str:
    if state.get("ambiguous_candidates"):
        return "ambiguous"
    return "ok"


@dataclass
class GraphPipeline:
    """Wrapper que ejecuta el grafo y devuelve `GraphOutput`."""

    compiled: Any  # CompiledGraph de LangGraph
    agent_config_repository: AgentConfigRepository
    rag_settings: RagSettings

    async def run(
        self,
        *,
        query: str,
        allowed_countries: list[str],
        system_prompt: str,
        conversation_id: UUID | None = None,
        inherited_product_id: UUID | None = None,
    ) -> GraphOutput:
        agent_cfg = await self.agent_config_repository.get_active(
            rag_fallback=self.rag_settings
        )
        state = initial_state(
            query=query,
            allowed_countries=list(allowed_countries),
            system_prompt=system_prompt,
            conversation_id=conversation_id,
            inherited_product_id=inherited_product_id,
            classifier_system_prompt=agent_cfg.classifier_system_prompt,
            classifier_cache_namespace=agent_cfg.cache_namespace,
            runtime_full_corpus=agent_cfg.full_corpus_for_all_intents,
            intent_kinds_by_slug=agent_cfg.intent_kinds_by_slug,
            retrieval_top_k=agent_cfg.top_k,
            retrieval_candidate_k=agent_cfg.candidate_k,
        )
        final: dict[str, Any] = await self.compiled.ainvoke(state)
        return GraphOutput(
            retrieved=list(final.get("retrieved") or []),
            top_similarity=float(final.get("top_similarity") or 0.0),
            answer_text=final.get("answer_text"),
            citations=list(final.get("citations") or []),
            intent=final.get("intent"),
            product_id=final.get("product_id"),
            product_name=final.get("product_name"),
            product_inherited=bool(final.get("product_inherited") or False),
            ambiguous_candidates=list(final.get("ambiguous_candidates") or []),
            graph_trace=list(final.get("trace") or []),
            error=final.get("error"),
        )
