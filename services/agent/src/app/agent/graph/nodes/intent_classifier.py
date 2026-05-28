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

# Bump al cambiar _SYSTEM_PROMPT para no reutilizar cache in-process viejo.
_INTENT_PROMPT_VERSION = "2026-05-28-indicaciones"

_SYSTEM_PROMPT = """\
Sos un clasificador de intencion para un agente veterinario de productos
(fichas tecnicas, bitacoras, balotarios). Etiquetas posibles (devolve EXACTAMENTE una):

- dosage_question: dosis, cuanto administrar, presentaciones, via o modo de
  administracion, frecuencia, duracion del tratamiento, uso operativo del producto,
  indicacion o indicaciones terapeuticas/de uso, para que sirve, en que casos o
  enfermedades se utiliza, si aplica en una especie o edad (cuando el foco no es
  solo riesgo/seguridad).
- clinical_protocol: protocolo terapeutico nombrado o esquema de tratamiento
  (ej. DAPP, desparasitacion en etapas), pasos de un protocolo clinico.
- comparison_with_competitor: comparacion con otro producto (Bravecto, Atrevia, etc).
- safety_question: efectos adversos, reacciones adversas/eventos adversos,
  tolerancia, contraindicaciones, toxicidad, sobredosis, interacciones,
  seguridad en gestacion/lactancia, uso en hepaticos/renales, edades minimas,
  collies/blancos/MDR1 cuando el foco sea riesgo clinico para el paciente.
- chitchat: saludo o conversacion casual sin consulta clinica.
- out_of_scope: SOLO temas ajenos al dominio veterinario-farmaceutico del agente
  (politica, geografia, recetas de medicina humana, chistes, etc.).

Reglas obligatorias:
- NO uses out_of_scope si la pregunta trata de un producto veterinario, parasitos,
  especie, administracion, indicaciones, dosis o seguridad del producto, aunque
  el nombre comercial no te resulte familiar.
- Si dudas entre out_of_scope y cualquier otra etiqueta, elegi la etiqueta de
  dominio veterinario (nunca out_of_scope).
- "indicacion" / "indicaciones" / "para que sirve" / "en que casos se usa" sobre
  un producto -> dosage_question (salvo que pida explicitamente un protocolo
  nombrado -> clinical_protocol).

Ejemplos:
- "Cual es la indicacion de Imperia?" -> dosage_question
- "En que casos se puede utilizar Imperia?" -> dosage_question
- "Cual es el protocolo para DAPP?" -> clinical_protocol
- "Cuales son las contraindicaciones de Imperia?" -> safety_question
- "Hola, como estas?" -> chitchat
- "Cual es la capital de Francia?" -> out_of_scope

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
    cache_namespace: str = _INTENT_PROMPT_VERSION

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
