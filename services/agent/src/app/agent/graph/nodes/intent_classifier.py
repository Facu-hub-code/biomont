"""IntentClassifier (spec 003/008): clasifica el mensaje del usuario."""

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

    if adjusted.intent == Intent.dosage_question and _dose_calculation_signals(nq):
        return IntentClassification(
            intent=Intent.dose_calculation,
            confidence=max(adjusted.confidence, 0.85),
        )

    return adjusted


def _dose_calculation_signals(normalized_query: str) -> bool:
    q = normalized_query
    has_weight = "kg" in q or "kilo" in q
    calc_words = (
        "calcular",
        "cuanto ml",
        "cuantos ml",
        "que tableta",
        "que presentacion",
        "que comprimido",
        "volumen",
        "cuantas tabletas",
    )
    return has_weight and any(w in q for w in calc_words)


@dataclass
class IntentClassifierNode:
    chat_model: BaseChatModel

    def __post_init__(self) -> None:
        self._cache: dict[str, IntentClassification] = {}

    async def __call__(self, state: dict) -> dict:
        query = state.get("query") or ""
        system_prompt = state.get("classifier_system_prompt") or ""
        cache_namespace = state.get("classifier_cache_namespace") or "default"
        cache_key = _cache_key(cache_namespace, query)
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

            if not system_prompt.strip():
                result["outcome"] = "fallback_out_of_scope"
                updates["intent"] = Intent.out_of_scope
                updates["intent_confidence"] = 0.0
                return updates

            try:
                structured = self.chat_model.with_structured_output(
                    IntentClassification
                )
                response = await structured.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
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
