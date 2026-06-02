"""IntentClassifier (spec 003/008): clasifica el mensaje del usuario."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from biomont_common.db.product_repository import normalize_text
from biomont_common.dosing.extractors import extract_dosing_context
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import Intent, IntentClassification

from app.agent.graph.nodes._helpers import trace_node

_logger = get_logger("agent.graph.intent")

# Posologia narrativa sin calculo por peso (spec 011 CA-9).
_DOSAGE_INFO_ONLY_MARKERS = (
    "con o sin alimento",
    "cada cuantas horas",
    "cada cuanto",
    "gestacion",
    "embaraz",
    "partir la tableta",
    "partir tableta",
    "ranura",
    "via de administr",
    "como se administra",
    "posologia general",
)

# Frases de eleccion de presentacion / cantidad segun peso.
_DOSE_CALC_PHRASES = (
    "calcular",
    "cuanto ml",
    "cuantos ml",
    "cuanta ml",
    "que tableta",
    "que presentacion",
    "que comprimido",
    "que comprimidos",
    "cuantas tabletas",
    "cuanta tableta",
    "que dosis",
    "cuanta dosis",
    "cuanto dosis",
    "le doy",
    "le damos",
    "debo dar",
    "debo administrar",
    "darle",
    "administrarle",
    "volumen",
    "necesito dar",
    "cuanto le doy",
    "cuanta le doy",
)

_DOSE_GIVE_VERBS = (
    "le doy",
    "le damos",
    "debo dar",
    "darle",
    "administro",
    "administrar",
)


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


def _dose_calculation_informational_only(normalized_query: str) -> bool:
    """True si la pregunta es informativa (RAG), no calculo por peso."""

    q = normalized_query
    if ("indicacion" in q or "indicaciones" in q) and "kg" not in q and "kilo" not in q:
        return True
    return any(marker in q for marker in _DOSAGE_INFO_ONLY_MARKERS)


def _has_parseable_weight(query: str, normalized_query: str) -> bool:
    ctx = extract_dosing_context(query)
    if ctx.weight_kg is not None:
        return True
    return "kg" in normalized_query or "kilo" in normalized_query


def dose_calculation_signals(raw_query: str) -> bool:
    """Detecta preguntas del tipo 'perro 25 kg, que Proteggo/tableta le doy'."""

    nq = normalize_text(raw_query)
    if not nq or _dose_calculation_informational_only(nq):
        return False
    if not _has_parseable_weight(raw_query, nq):
        return False
    if any(phrase in nq for phrase in _DOSE_CALC_PHRASES):
        return True
    # Caso natural: "que dosis de X le doy a un perro de 25 kg" (golden dose-proteggo-3m).
    if "dosis" in nq and any(verb in nq for verb in _DOSE_GIVE_VERBS):
        return True
    return False


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

    if dose_calculation_signals(raw_query):
        if adjusted.intent in (
            Intent.dosage_question,
            Intent.out_of_scope,
            Intent.chitchat,
        ):
            return IntentClassification(
                intent=Intent.dose_calculation,
                confidence=max(adjusted.confidence, 0.85),
            )

    return adjusted


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
