"""DoseCalculator: motor determinista de dosis (spec 011)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from biomont_common.db.dosing_repository import DosingRepository
from biomont_common.dosing.calculator import calculate_dose, format_dose_response
from biomont_common.schemas.dosing import DoseCalculationError

from app.agent.graph.nodes._helpers import trace_node


@dataclass
class DoseCalculatorNode:
    dosing_repository: DosingRepository

    async def __call__(self, state: dict) -> dict:
        updates: dict = {}
        product_id = state.get("product_id")
        product_name = state.get("product_name") or "producto"
        species = state.get("dose_species")
        weight_raw = state.get("dose_weight_kg")
        age_weeks = state.get("dose_age_weeks")

        with trace_node(updates, node="DoseCalculator") as result:
            if product_id is None or species is None or weight_raw is None:
                updates["answer_text"] = (
                    "No pude calcular la dosis porque faltan datos del producto, "
                    "especie o peso."
                )
                updates["structured_response"] = True
                result["outcome"] = "missing_inputs"
                return updates

            profile = await self.dosing_repository.get_published_profile(
                UUID(str(product_id)), species
            )
            if profile is None:
                available = await self.dosing_repository.list_species_for_product(
                    UUID(str(product_id))
                )
                hint = ""
                if available:
                    hint = f" Especies disponibles: {', '.join(available)}."
                updates["answer_text"] = (
                    f"No hay perfil de dosis publicado para *{product_name}* "
                    f"en especie '{species}'.{hint}"
                )
                updates["structured_response"] = True
                result["outcome"] = "no_profile"
                return updates

            rules = await self.dosing_repository.list_published_rules(
                profile.id, profile.published_version
            )
            outcome = calculate_dose(
                profile=profile,
                rules=rules,
                product_id=UUID(str(product_id)),
                product_name=product_name,
                weight_kg=Decimal(str(weight_raw)),
                species=species,
                age_weeks=age_weeks,
            )

            if isinstance(outcome, DoseCalculationError):
                updates["answer_text"] = outcome.message
                updates["structured_response"] = True
                result["outcome"] = outcome.code
                return updates

            updates["answer_text"] = format_dose_response(outcome)
            updates["structured_response"] = True
            result["outcome"] = "calculated"
            result["payload"] = outcome.model_dump(mode="json")
        return updates
