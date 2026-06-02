"""CommercialComparisonDiff: diff determinista del cuadro comercial (spec 012)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from biomont_common.db.comparison_repository import (
    ComparisonRepository,
    format_comparison_diff,
)

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class CommercialComparisonDiffNode:
    comparison_repository: ComparisonRepository

    async def __call__(self, state: dict) -> dict:
        updates: dict = {}
        with trace_node(updates, node="CommercialComparisonDiff") as result:
            subject_id = state.get("product_id")
            subject_name = state.get("product_name") or "producto Biomont"
            competitor_name = state.get("competitor_name") or ""
            competitor_id = state.get("competitor_id")
            competitor_product_id = state.get("competitor_product_id")

            if subject_id is None or not competitor_name:
                updates["answer_text"] = (
                    "No pude completar la comparacion por falta de productos."
                )
                updates["structured_response"] = True
                result["outcome"] = "missing_inputs"
                return updates

            set_row = await self.comparison_repository.get_published_set(
                UUID(str(subject_id))
            )
            if set_row is None:
                updates["answer_text"] = (
                    f"No hay cuadro comparativo comercial publicado para "
                    f"*{subject_name}*."
                )
                updates["structured_response"] = True
                result["outcome"] = "no_set"
                return updates

            if set_row["completeness_status"] != "complete":
                updates["answer_text"] = (
                    f"El cuadro comparativo de *{subject_name}* esta incompleto. "
                    f"El equipo debe completarlo en el backoffice."
                )
                updates["structured_response"] = True
                result["outcome"] = "incomplete_set"
                return updates

            diff = await self.comparison_repository.diff_rows(
                subject_product_id=UUID(str(subject_id)),
                subject_product_name=subject_name,
                competitor_name=competitor_name,
                competitor_id=(
                    UUID(str(competitor_id)) if competitor_id else None
                ),
                linked_product_id=(
                    UUID(str(competitor_product_id))
                    if competitor_product_id
                    else None
                ),
            )

            if diff is None:
                updates["answer_text"] = (
                    f"No encontre a *{competitor_name}* en el cuadro comparativo "
                    f"de *{subject_name}*."
                )
                updates["structured_response"] = True
                result["outcome"] = "competitor_row_missing"
                return updates

            updates["answer_text"] = format_comparison_diff(diff)
            updates["structured_response"] = True
            result["outcome"] = "diff_ready"
            result["payload"] = {
                "differences_count": len(diff.differences),
                "version": diff.published_version,
            }
        return updates
