"""FAQRetriever (spec 003): retrieval directo del balotario.

Si top-1 supera `FAQ_DIRECT_THRESHOLD`, el grafo corto-circuita y
responde con la entrada canonica (sin invocar al Answerer LLM).
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.embeddings import Embeddings

from biomont_common.db.faq_repository import FaqRepository
from biomont_common.schemas.agent_graph import Intent

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class FaqRetrieverNode:
    repository: FaqRepository
    embeddings: Embeddings
    vector_weight: float
    bm25_weight: float
    direct_threshold: float = 0.80
    top_k: int = 3
    #: Si True, consulta FAQ para cualquier intent (útiles para prueba del corpus completo).
    full_corpus_for_all_intents: bool = False

    async def __call__(self, state: dict) -> dict:
        intent = state.get("intent")
        product_id = state.get("product_id")
        updates: dict = {"faq_hits": [], "faq_direct_answer": None}
        with trace_node(updates, node="FAQRetriever") as result:
            # Si el intent es claramente otro, no toco el FAQ retrieval para
            # no introducir respuestas canonicas fuera de contexto.
            if (
                not self.full_corpus_for_all_intents
                and intent not in (Intent.faq, Intent.safety_question)
            ):
                result["outcome"] = "skipped"
                return updates

            query = state.get("query") or ""
            embedding = await self.embeddings.aembed_query(query)
            hits = await self.repository.search(
                query_text=query,
                query_embedding=embedding,
                product_id=product_id,
                vector_weight=self.vector_weight,
                bm25_weight=self.bm25_weight,
                top_k=self.top_k,
            )
            if not hits:
                result["outcome"] = "no_hits"
                return updates

            top = hits[0]
            direct = top.answer if top.final_score >= self.direct_threshold else None
            result["outcome"] = "direct_hit" if direct else "soft_hit"
            result["payload"] = {
                "top_score": top.final_score,
                "faq_id": str(top.faq_id),
                "direct": bool(direct),
            }
            updates["faq_hits"] = hits
            updates["faq_direct_answer"] = direct
        return updates
