"""Ensamblado del system prompt del IntentClassifier (spec 008)."""

from __future__ import annotations

from dataclasses import dataclass

CLASSIFIER_RULES_SUFFIX = """
Reglas obligatorias:
- NO uses out_of_scope si la pregunta trata de un producto veterinario, parasitos,
  especie, administracion, indicaciones, dosis o seguridad del producto, aunque
  el nombre comercial no te resulte familiar.
- Si dudas entre out_of_scope y cualquier otra etiqueta, elegi la etiqueta de
  dominio veterinario (nunca out_of_scope).
- "indicacion" / "indicaciones" / "para que sirve" / "en que casos se usa" sobre
  un producto -> dosage_question (salvo que pida explicitamente un protocolo
  nombrado -> clinical_protocol).
- Si menciona peso en kg (ej. 25 kg, 25kg) y pide que dosis/tableta/presentacion
  dar o "le doy" para un animal -> dose_calculation (motor determinista), NO
  dosage_question.
- dosage_question solo cuando la dosis es informativa sin calculo por peso
  (administracion con alimento, posologia en gestacion, etc.).

Ejemplos:
- "Que dosis de Proteggo 3M le doy a un perro de 25 kg?" -> dose_calculation
- "Perro de 25 kg, que tableta de MARVO 20 le doy?" -> dose_calculation
- "Cual es la indicacion de Imperia?" -> dosage_question
- "En que casos se puede utilizar Imperia?" -> dosage_question
- "Cual es el protocolo para DAPP?" -> clinical_protocol
- "Cuales son las contraindicaciones de Imperia?" -> safety_question
- "Hola, como estas?" -> chitchat
- "Cual es la capital de Francia?" -> out_of_scope

Devolve JSON valido siguiendo el schema dado, sin texto extra.
"""


@dataclass(frozen=True, slots=True)
class IntentPromptLine:
    intent_slug: str
    classifier_hint: str
    is_enabled: bool
    sort_order: int


def build_classifier_system_prompt(
    *,
    preamble: str | None,
    intents: list[IntentPromptLine],
) -> str:
    """Arma el prompt del clasificador desde filas habilitadas."""

    intro = (preamble or "").strip() or (
        "Sos un clasificador de intencion para un agente veterinario de productos "
        "(fichas tecnicas, bitacoras, balotarios)."
    )
    enabled = [i for i in intents if i.is_enabled]
    enabled.sort(key=lambda x: x.sort_order)
    bullets = "\n".join(
        f"- {line.intent_slug}: {line.classifier_hint.strip()}" for line in enabled
    )
    return (
        f"{intro}\n"
        "Etiquetas posibles (devolve EXACTAMENTE una):\n\n"
        f"{bullets}\n\n"
        f"{CLASSIFIER_RULES_SUFFIX.strip()}\n"
    )
