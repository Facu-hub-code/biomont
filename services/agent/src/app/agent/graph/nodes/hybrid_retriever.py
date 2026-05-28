"""HybridRetriever (spec 003): vector + BM25 con score ponderado."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.embeddings import Embeddings

from biomont_common.db.rag_repository import RagRepository

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class HybridRetrieverNode:
    repository: RagRepository
    embeddings: Embeddings
    vector_weight: float
    bm25_weight: float
    top_k: int
    candidate_k: int

    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        allowed = state.get("allowed_countries") or []
        product_id = state.get("product_id")
        kinds = state.get("filter_kinds")

        updates: dict = {"retrieved": [], "top_similarity": 0.0}
        with trace_node(updates, node="HybridRetriever") as result:
            embedding = await self.embeddings.aembed_query(query)
            top_k = int(state.get("retrieval_top_k") or self.top_k)
            candidate_k = int(state.get("retrieval_candidate_k") or self.candidate_k)
            hits = await self.repository.search_hybrid_chunks(
                query_text=query,
                query_embedding=embedding,
                allowed_countries=allowed,
                product_id=product_id,
                kinds=kinds,
                vector_weight=self.vector_weight,
                bm25_weight=self.bm25_weight,
                top_k=top_k,
                candidate_k=candidate_k,
            )

            top_similarity = hits[0].final_score if hits else 0.0
            result["outcome"] = "retrieved" if hits else "empty"
            result["payload"] = {
                "count": len(hits),
                "top_scores": [
                    {
                        "chunk_id": str(h.chunk_id),
                        "vec": h.vector_score,
                        "bm25": h.bm25_score,
                        "final": h.final_score,
                    }
                    for h in hits[:5]
                ],
            }
            updates["retrieved"] = hits
            updates["top_similarity"] = top_similarity
        return updates
