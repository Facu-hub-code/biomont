"""CompetitorResolver: identifica producto competidor (spec 012)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from biomont_common.db.comparison_repository import ComparisonRepository
from biomont_common.db.product_repository import ProductRepository, normalize_text

from app.agent.graph.nodes._helpers import trace_node

_COMPARE_RE = re.compile(
    r"\b(vs\.?|versus|contra|comparar?\w*|frente a)\b",
    re.IGNORECASE,
)


@dataclass
class CompetitorResolverNode:
    comparison_repository: ComparisonRepository
    product_repository: ProductRepository

    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        updates: dict = {}
        with trace_node(updates, node="CompetitorResolver") as result:
            subject_id = state.get("product_id")
            subject_name = state.get("product_name") or ""

            if subject_id is None:
                updates["answer_text"] = (
                    "Para comparar productos necesito que indiques el producto Biomont."
                )
                updates["structured_response"] = True
                result["outcome"] = "missing_subject"
                return updates

            second_product = await self._resolve_second_biomont_product(
                query, UUID(str(subject_id))
            )
            if second_product is not None:
                updates["competitor_product_id"] = second_product["id"]
                updates["competitor_name"] = second_product["name"]
                updates["competitor_is_internal"] = True
                result["outcome"] = "internal_product"
                result["payload"] = {"competitor": second_product["name"]}
                return updates

            competitor = await self._resolve_competitor_name(query, subject_name)
            if competitor is None:
                updates["answer_text"] = (
                    "¿Con que producto queres comparar? Indica el nombre del "
                    "competidor (ej. Apoquel, Bravecto, Marboxi)."
                )
                updates["structured_response"] = True
                result["outcome"] = "needs_competitor"
                return updates

            updates["competitor_id"] = competitor.id
            updates["competitor_name"] = competitor.name
            updates["competitor_is_internal"] = competitor.is_internal
            if competitor.linked_product_id:
                updates["competitor_product_id"] = competitor.linked_product_id
            result["outcome"] = "resolved"
            result["payload"] = {"competitor": competitor.name}
        return updates

    async def _resolve_second_biomont_product(
        self, query: str, exclude_id: UUID
    ) -> dict | None:
        candidates = await self.product_repository.search_candidates(
            query, allowed_countries=[], limit=5
        )
        for c in candidates:
            if c.product_id != exclude_id and c.similarity >= 0.55:
                return {"id": c.product_id, "name": c.product_name}
        return None

    async def _resolve_competitor_name(self, query: str, subject_name: str):
        nq = normalize_text(query)
        subject_norm = normalize_text(subject_name)
        tokens = [t for t in re.split(r"[\s,/]+", nq) if len(t) >= 3]
        best = None
        best_sim = 0.0

        for token in tokens:
            if token in subject_norm:
                continue
            matches = await self.comparison_repository.find_competitor_by_query(token)
            for m in matches:
                sim = len(set(token) & set(normalize_text(m.name))) / max(
                    len(token), 1
                )
                if sim > best_sim:
                    best_sim = sim
                    best = m

        if best is not None:
            return best

        if _COMPARE_RE.search(query):
            parts = _COMPARE_RE.split(query, maxsplit=1)
            if len(parts) > 1:
                tail = parts[-1].strip()
                matches = await self.comparison_repository.find_competitor_by_query(
                    tail[:80]
                )
                if matches:
                    return matches[0]
        return None
