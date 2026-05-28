"""IntentClassifier (spec 003): clasifica el mensaje del usuario."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from biomont_common.db.product_repository import normalize_text
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import Intent, IntentClassification

from app.agent.graph.nodes._helpers import trace_node

_logger = get_logger("agent.graph.intent")

_SYSTEM_PROMPT = """\
Sos un clasificador de intencion para un agente veterinario.
Etiquetas posibles (devolve EXACTAMENTE una):

- dosage_question: pregunta sobre dosis, cuanto administrar, presentaciones,
  modo de administracion o uso operativo del producto.
- clinical_protocol: pregunta sobre protocolos terapeuticos / tratamiento clinico.
- comparison_with_competitor: comparacion con otro producto (Bravecto, Atrevia, etc).
- safety_question: efectos adversos, reacciones adversas/eventos adversos,
  tolerancia, contraindicaciones, toxicidad, sobredosis, interacciones,
  seguridad en gestacion/lactancia, uso en hepaticos/renales, edades minimas,
  collies/blancos/MDR1 cuando el foco sea riesgo clinico para el paciente.
- chitchat: saludo o conversacion casual.
- out_of_scope: fuera del dominio (politica, recetas humanas, etc).

Devolve JSON valido siguiendo el schema dado, sin texto extra.
"""


def lexical_safety_signals_present(normalized_query: str) -> bool:
    """Señales baratas cuando el modelo subclasifica riesgo como otro intent."""

    q = normalized_query.casefold()

    if "advers" in q and (
        "efect" in q or "reacci" in q or "event" in q
    ):
        return True
    if "contrai" in q:
        return True
    if "toxic" in q or "intoxic" in q or "sobredosi" in q:
        return True
    if "mdr1" in q or "multidrog" in q:
        return True
    return any(w in q for w in ("collie", "colie", "pastor ingles"))


def apply_intent_lexical_calibration(
    classification: IntentClassification, raw_query: str
) -> IntentClassification:
    """Corrige errores conocidos despues del LLM antes de rutear retrieval."""

    nq = normalize_text(raw_query)
    adjusted = classification

    if adjusted.intent == Intent.dosage_question and lexical_safety_signals_present(
        nq
    ):
        return IntentClassification(
            intent=Intent.safety_question,
            confidence=max(adjusted.confidence, 0.88),
        )

    return adjusted


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
                calibrated = apply_intent_lexical_calibration(cached, query)
                result["outcome"] = "cache_hit"
                result["payload"] = {"intent": calibrated.intent.value}
                updates["intent"] = calibrated.intent
                updates["intent_confidence"] = calibrated.confidence
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

            coerced = _coerce_response(response)
            calibrated = apply_intent_lexical_calibration(coerced, query)
            self._cache[cache_key] = calibrated
            result["outcome"] = "classified"
            result["payload"] = {"intent": calibrated.intent.value}
            updates["intent"] = calibrated.intent
            updates["intent_confidence"] = calibrated.confidence
        return updates


def _coerce_response(response: object) -> IntentClassification:
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
