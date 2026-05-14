"""Calculator (spec 003): placeholder del futuro motor de calculo.

Declarado como nodo del grafo para que el contrato de la spec quede en el
codigo, pero no se enruta hacia el en v1. El motor real se especifica en
una spec aparte que tambien creara las tablas estructuradas (formulas,
dosing_ranges, etc).
"""

from __future__ import annotations

from dataclasses import dataclass


class CalculatorNotImplementedError(NotImplementedError):
    """Error controlado: el nodo existe pero no se enruta en v1."""


@dataclass
class CalculatorNode:
    async def __call__(self, state: dict) -> dict:
        # No deberia ser invocado por el StateGraph en v1 (no hay ruta hacia
        # este nodo). Si alguien lo enruta manualmente, falla con error
        # claro para no producir respuestas silenciosamente vacias.
        raise CalculatorNotImplementedError(
            "Calculator node es placeholder; motor de calculo no implementado en v1"
        )
