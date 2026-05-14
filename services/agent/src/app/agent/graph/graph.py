"""Composicion del grafo LangGraph del agente (spec 003).

Diagrama:

    IntentClassifier
        |
        v
    ProductResolver --(ambiguous)--> END (con mensaje de aclaracion)
        |
        v
    MetaFilter
        |
        v
    FAQRetriever --(direct hit)--> Answerer --> StateUpdater --> END
        |
        | (no direct)
        v
    HybridRetriever --> Answerer --> StateUpdater --> END

El nodo `CalculatorNode` queda registrado pero no se enruta en v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)
from biomont_common.db.faq_repository import FaqRepository
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import RagRepository
from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import GraphNodeTrace, Intent
from biomont_common.schemas.knowledge import FaqHit, HybridChunkHit
from biomont_common.schemas.products import ProductCandidate
from biomont_common.settings import RagSettings, get_rag_settings

from app.agent.graph.nodes import (
    AnswererNode,
    FaqRetrieverNode,
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
    """Salida del grafo, compatible (en forma) con `PipelineOutput`.

    Mantenemos campos que el orchestrator ya consume (`retrieved`,
    `top_similarity`, `answer`, `error`) y agregamos los que el grafo
    aporta (`intent`, `product_id`, `graph_trace`, `ambiguous_candidates`).
    """

    retrieved: list[HybridChunkHit]
    top_similarity: float
    answer_text: str | None
    citations: list[dict[str, Any]]
    intent: Intent | None
    product_id: UUID | None
    product_inherited: bool
    ambiguous_candidates: list[ProductCandidate]
    faq_hits: list[FaqHit]
    faq_direct_answer: str | None
    graph_trace: list[GraphNodeTrace]
    error: str | None = None


def build_graph(
    *,
    rag_repository: RagRepository,
    product_repository: ProductRepository,
    faq_repository: FaqRepository,
    state_repository: ConversationStateRepository,
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
        "MetaFilter": MetaFilterNode(),
        "FAQRetriever": FaqRetrieverNode(
            repository=faq_repository,
            embeddings=embeddings,
            vector_weight=cfg.vector_weight,
            bm25_weight=cfg.bm25_weight,
            direct_threshold=cfg.faq_direct_threshold,
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

    graph.add_edge("MetaFilter", "FAQRetriever")

    graph.add_conditional_edges(
        "FAQRetriever",
        _route_after_faq,
        {
            "answer": "Answerer",
            "hybrid": "HybridRetriever",
        },
    )

    graph.add_edge("HybridRetriever", "Answerer")
    graph.add_edge("Answerer", "StateUpdater")
    graph.add_edge("StateUpdater", END)

    compiled = graph.compile()
    return GraphPipeline(compiled=compiled)


def _route_after_resolver(state: dict) -> str:
    if state.get("ambiguous_candidates"):
        return "ambiguous"
    return "ok"


def _route_after_faq(state: dict) -> str:
    if state.get("faq_direct_answer"):
        return "answer"
    return "hybrid"


@dataclass
class GraphPipeline:
    """Wrapper que ejecuta el grafo y devuelve `GraphOutput`."""

    compiled: Any  # CompiledGraph de LangGraph

    async def run(
        self,
        *,
        query: str,
        allowed_countries: list[str],
        system_prompt: str,
        conversation_id: UUID | None = None,
        inherited_product_id: UUID | None = None,
    ) -> GraphOutput:
        state = initial_state(
            query=query,
            allowed_countries=list(allowed_countries),
            system_prompt=system_prompt,
            conversation_id=conversation_id,
            inherited_product_id=inherited_product_id,
        )
        final: dict[str, Any] = await self.compiled.ainvoke(state)
        return GraphOutput(
            retrieved=list(final.get("retrieved") or []),
            top_similarity=float(final.get("top_similarity") or 0.0),
            answer_text=final.get("answer_text"),
            citations=list(final.get("citations") or []),
            intent=final.get("intent"),
            product_id=final.get("product_id"),
            product_inherited=bool(final.get("product_inherited") or False),
            ambiguous_candidates=list(final.get("ambiguous_candidates") or []),
            faq_hits=list(final.get("faq_hits") or []),
            faq_direct_answer=final.get("faq_direct_answer"),
            graph_trace=list(final.get("trace") or []),
            error=final.get("error"),
        )
