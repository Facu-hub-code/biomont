"""IntentClassifier (spec 003): clasifica el mensaje del usuario.

Taxonomia cerrada definida en `biomont_common.schemas.agent_graph.Intent`.
Modelo: `gpt-4o-mini` con structured output (json_schema). Si la red
falla o el LLM devuelve algo invalido, retornamos `out_of_scope` (no
queremos bloquear el grafo entero por un error de clasificador).

Cache simple por hash(query + prompt_version) durante la vida del
proceso. Si en el futuro se requiere TTL/eviction, mover a un store
explicito.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import Intent, IntentClassification

from app.agent.graph.nodes._helpers import trace_node

_logger = get_logger("agent.graph.intent")

_SYSTEM_PROMPT = """\
Sos un clasificador de intencion para un agente veterinario.
Etiquetas posibles (devolve EXACTAMENTE una):

- dosage_question: pregunta sobre dosis o cuanto administrar.
- clinical_protocol: pregunta sobre protocolos terapeuticos / tratamiento clinico.
- comparison_with_competitor: comparacion con otro producto (Bravecto, Atrevia, etc).
- safety_question: gestacion, lactancia, edad, MDR1, hepatopatas.
- faq: preguntas frecuentes recurrentes (uso comun, sabor, presentaciones).
- chitchat: saludo o conversacion casual.
- out_of_scope: fuera del dominio (politica, recetas humanas, etc).

Devolve JSON valido siguiendo el schema dado, sin texto extra.
"""


@dataclass
class IntentClassifierNode:
    chat_model: BaseChatModel
    cache_namespace: str = "default"

    def __post_init__(self) -> None:
        self._cache: dict[str, IntentClassification] = {}

    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        cache_key = _cache_key(self.cache_namespace, query)
        updates: dict = {}
        with trace_node(updates, node="IntentClassifier") as result:
            cached = self._cache.get(cache_key)
            if cached is not None:
                result["outcome"] = "cache_hit"
                result["payload"] = {"intent": cached.intent.value}
                updates["intent"] = cached.intent
                updates["intent_confidence"] = cached.confidence
                return updates

            try:
                structured = self.chat_model.with_structured_output(
                    IntentClassification
                )
                response = await structured.ainvoke(
                    [
                        SystemMessage(content=_SYSTEM_PROMPT),
                        HumanMessage(content=query),
                    ]
                )
            except Exception as exc:
                _logger.warning(
                    "intent_classifier_failed",
                    action="classify",
                    error=str(exc)[:200],
                )
                result["outcome"] = "fallback_out_of_scope"
                updates["intent"] = Intent.out_of_scope
                updates["intent_confidence"] = 0.0
                return updates

            normalized = _coerce_response(response)
            self._cache[cache_key] = normalized
            result["outcome"] = "classified"
            result["payload"] = {"intent": normalized.intent.value}
            updates["intent"] = normalized.intent
            updates["intent_confidence"] = normalized.confidence
        return updates


def _coerce_response(response: object) -> IntentClassification:
    """Acepta dict / IntentClassification / objeto con .intent (duck typing).

    Hace al nodo tolerante a fakes de tests que solo proveen `.intent`.
    """

    if isinstance(response, IntentClassification):
        return response
    if isinstance(response, dict):
        try:
            return IntentClassification(**response)
        except Exception:
            return IntentClassification(
                intent=Intent.out_of_scope, confidence=0.0
            )
    intent = getattr(response, "intent", None)
    if isinstance(intent, Intent):
        confidence = float(getattr(response, "confidence", 1.0) or 1.0)
        return IntentClassification(intent=intent, confidence=confidence)
    if isinstance(intent, str):
        try:
            return IntentClassification(intent=Intent(intent), confidence=1.0)
        except ValueError:
            pass
    return IntentClassification(intent=Intent.out_of_scope, confidence=0.0)


def _cache_key(namespace: str, query: str) -> str:
    digest = hashlib.sha256(f"{namespace}|{query}".encode("utf-8")).hexdigest()
    return digest[:32]
