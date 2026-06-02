"""Composicion del grafo LangGraph del agente (spec 003 + sprint 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from biomont_common.db.agent_config_repository import AgentConfigRepository
from biomont_common.db.comparison_repository import ComparisonRepository
from biomont_common.db.conversation_state_repository import (
    ConversationStateRepository,
)
from biomont_common.db.dosing_repository import DosingRepository
from biomont_common.db.product_repository import ProductRepository
from biomont_common.db.rag_repository import RagRepository
from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import GraphNodeTrace, Intent
from biomont_common.schemas.knowledge import HybridChunkHit
from biomont_common.schemas.products import ProductCandidate
from biomont_common.settings import RagSettings, get_rag_settings

from app.agent.graph.nodes.answerer import AnswererNode
from app.agent.graph.nodes.calculator import DoseCalculatorNode
from app.agent.graph.nodes.commercial_comparison_diff import (
    CommercialComparisonDiffNode,
)
from app.agent.graph.nodes.competitor_resolver import CompetitorResolverNode
from app.agent.graph.nodes.hybrid_retriever import HybridRetrieverNode
from app.agent.graph.nodes.intent_classifier import IntentClassifierNode
from app.agent.graph.nodes.meta_filter import MetaFilterNode
from app.agent.graph.nodes.product_resolver import ProductResolverNode
from app.agent.graph.nodes.state_updater import StateUpdaterNode
from app.agent.graph.nodes.weight_species_extractor import (
    WeightSpeciesExtractorNode,
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
    structured_response: bool = False
    error: str | None = None


def build_graph(
    *,
    rag_repository: RagRepository,
    product_repository: ProductRepository,
    dosing_repository: DosingRepository,
    comparison_repository: ComparisonRepository,
    state_repository: ConversationStateRepository,
    agent_config_repository: AgentConfigRepository,
    embeddings: Embeddings,
    chat_model: BaseChatModel,
    settings: RagSettings | None = None,
) -> "GraphPipeline":
    """Compila el grafo con los nodos parametrizados."""

    cfg = settings or get_rag_settings()

    graph: StateGraph = StateGraph(AgentGraphState)

    graph.add_node("IntentClassifier", IntentClassifierNode(chat_model=chat_model))
    graph.add_node(
        "ProductResolver",
        ProductResolverNode(
            repository=product_repository,
            threshold=cfg.product_resolver_threshold,
            margin=cfg.product_resolver_margin,
        ),
    )
    graph.add_node(
        "WeightSpeciesExtractor",
        WeightSpeciesExtractorNode(),
    )
    graph.add_node(
        "DoseCalculator",
        DoseCalculatorNode(dosing_repository=dosing_repository),
    )
    graph.add_node(
        "CompetitorResolver",
        CompetitorResolverNode(
            comparison_repository=comparison_repository,
            product_repository=product_repository,
        ),
    )
    graph.add_node(
        "CommercialComparisonDiff",
        CommercialComparisonDiffNode(comparison_repository=comparison_repository),
    )
    graph.add_node(
        "MetaFilter",
        MetaFilterNode(full_corpus_for_all_intents=cfg.full_corpus_for_all_intents),
    )
    graph.add_node(
        "HybridRetriever",
        HybridRetrieverNode(
            repository=rag_repository,
            embeddings=embeddings,
            vector_weight=cfg.vector_weight,
            bm25_weight=cfg.bm25_weight,
            top_k=cfg.top_k,
            candidate_k=cfg.candidate_k,
        ),
    )
    graph.add_node("Answerer", AnswererNode(chat_model=chat_model))
    graph.add_node("StateUpdater", StateUpdaterNode(repository=state_repository))

    graph.add_edge(START, "IntentClassifier")
    graph.add_edge("IntentClassifier", "ProductResolver")

    graph.add_conditional_edges(
        "ProductResolver",
        _route_after_resolver,
        {
            "ambiguous": END,
            "dose": "WeightSpeciesExtractor",
            "comparison": "CompetitorResolver",
            "rag": "MetaFilter",
        },
    )

    graph.add_conditional_edges(
        "WeightSpeciesExtractor",
        _route_after_extractor,
        {
            "repregunta": "StateUpdater",
            "calculate": "DoseCalculator",
        },
    )
    graph.add_edge("DoseCalculator", "StateUpdater")

    graph.add_conditional_edges(
        "CompetitorResolver",
        _route_after_competitor_resolver,
        {
            "repregunta": "StateUpdater",
            "diff": "CommercialComparisonDiff",
        },
    )
    graph.add_edge("CommercialComparisonDiff", "StateUpdater")

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
    intent = state.get("intent")
    if intent == Intent.dose_calculation:
        return "dose"
    if intent == Intent.comparison_with_competitor:
        return "comparison"
    return "rag"


def _route_after_extractor(state: dict) -> str:
    if state.get("answer_text") and state.get("structured_response"):
        return "repregunta"
    return "calculate"


def _route_after_competitor_resolver(state: dict) -> str:
    if state.get("answer_text") and state.get("structured_response"):
        return "repregunta"
    return "diff"


@dataclass
class GraphPipeline:
    """Wrapper que ejecuta el grafo y devuelve `GraphOutput`."""

    compiled: Any
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
        structured = bool(final.get("structured_response"))
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
            structured_response=structured,
            error=final.get("error"),
        )
