"""ProductResolver (spec 003): resolucion deterministica de producto.

Estrategia:
1. Match exacto sobre `product_aliases.normalized_alias` (pg_trgm).
2. Si no, top-N por `similarity()` (pg_trgm).
3. Si top-1 >= threshold y (top-1 - top-2) >= margin -> resolved.
4. Si la query no menciona producto pero hay `inherited_product_id` desde
   `conversation_state`, hereda.
5. Si nada cumple -> ambiguous con la lista de candidatos.

Sin LLM. Sin embeddings. Determinista.
"""

from __future__ import annotations

from dataclasses import dataclass

from biomont_common.db.product_repository import ProductRepository
from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.products import ProductCandidate

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class ProductResolverNode:
    repository: ProductRepository
    threshold: float = 0.55
    margin: float = 0.10
    top_n: int = 5

    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        intent = state.get("intent")
        allowed = state.get("allowed_countries") or []
        inherited = state.get("inherited_product_id")

        updates: dict = {
            "product_id": None,
            "product_name": None,
            "ambiguous_candidates": [],
            "product_inherited": False,
        }
        with trace_node(updates, node="ProductResolver") as result:
            if intent == Intent.chitchat:
                result["outcome"] = "skipped_chitchat"
                return updates

            candidates = await self.repository.search_candidates(
                query, allowed_countries=allowed, limit=self.top_n
            )

            if not candidates:
                if inherited is not None:
                    result["outcome"] = "inherited"
                    result["payload"] = {"product_id": str(inherited)}
                    product = await self.repository.get_by_id(inherited)
                    updates["product_id"] = inherited
                    updates["product_name"] = product.name if product else None
                    updates["product_inherited"] = True
                    return updates
                result["outcome"] = "no_candidates"
                return updates

            top = candidates[0]
            second_sim = candidates[1].similarity if len(candidates) > 1 else 0.0
            margin = top.similarity - second_sim

            if top.similarity >= self.threshold and margin >= self.margin:
                result["outcome"] = "resolved"
                result["payload"] = {
                    "product_id": str(top.product_id),
                    "similarity": top.similarity,
                    "margin": margin,
                }
                updates["product_id"] = top.product_id
                updates["product_name"] = top.product_name
                return updates

            if inherited is not None and top.similarity < self.threshold:
                result["outcome"] = "inherited_low_confidence"
                product = await self.repository.get_by_id(inherited)
                updates["product_id"] = inherited
                updates["product_name"] = product.name if product else None
                updates["product_inherited"] = True
                return updates

            result["outcome"] = "ambiguous"
            result["payload"] = {
                "candidates": [
                    {
                        "product_id": str(c.product_id),
                        "name": c.product_name,
                        "similarity": c.similarity,
                    }
                    for c in candidates[:3]
                ],
            }
            updates["ambiguous_candidates"] = _as_models(candidates[:3])
        return updates


def _as_models(items: list[ProductCandidate]) -> list[ProductCandidate]:
    """Devuelve los candidates como instancias pydantic explicitas.

    Soporta entrada como lista de modelos o de dicts (defensivo: si en el
    futuro el repositorio cambia el tipo de retorno, esto no rompe los
    nodos siguientes).
    """

    out: list[ProductCandidate] = []
    for it in items:
        if isinstance(it, ProductCandidate):
            out.append(it)
        elif isinstance(it, dict):
            out.append(ProductCandidate(**it))
    return out
