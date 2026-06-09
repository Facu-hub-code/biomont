"""WeightSpeciesExtractor: extrae peso y especie (spec 011)."""

from __future__ import annotations

from dataclasses import dataclass

from biomont_common.dosing.extractors import extract_dosing_context
from biomont_common.schemas.agent_graph import Intent

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class WeightSpeciesExtractorNode:
    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        updates: dict = {}
        with trace_node(updates, node="WeightSpeciesExtractor") as result:
            ctx = extract_dosing_context(query)
            if ctx.rejected_lb:
                updates["answer_text"] = (
                    "Para calcular la dosis necesito el *peso en kg* "
                    "(ej. 25 kg). En esta version no convierto libras automaticamente."
                )
                updates["structured_response"] = True
                result["outcome"] = "needs_weight_lb"
                return updates

            if ctx.needs_weight:
                product = state.get("product_name") or "el producto"
                updates["answer_text"] = (
                    f"Para indicarte la dosis correcta de *{product}*, necesito el "
                    f"*peso del animal en kg* (ej. 25 kg)."
                )
                updates["structured_response"] = True
                result["outcome"] = "needs_weight"
                return updates

            if ctx.needs_species:
                product = state.get("product_name") or "el producto"
                updates["answer_text"] = (
                    f"Para calcular la dosis de *{product}*, necesito saber la "
                    f"*especie* (ej. perro, gato, vaca, ternero)."
                )
                updates["structured_response"] = True
                result["outcome"] = "needs_species"
                return updates

            updates["dose_weight_kg"] = ctx.weight_kg
            updates["dose_species"] = ctx.species
            updates["dose_age_weeks"] = ctx.age_weeks
            result["outcome"] = "ok"
            result["payload"] = {
                "weight_kg": str(ctx.weight_kg),
                "species": ctx.species,
            }
        return updates
