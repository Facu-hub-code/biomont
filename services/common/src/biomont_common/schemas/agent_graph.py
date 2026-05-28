"""Schemas del grafo del agente (spec 003)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Taxonomia cerrada de intent del clasificador.

    Mantener sincronizada con prompts de IntentClassifier y con la
    columna `last_intent` de `conversation_state`.

    `safety_question` incluye farmacovigilancia (efectos adversos, toxicidad,
    contraindicaciones) y riesgos poblacionales cuando el foco no es solo FAQ
    de catalogo.
    """

    dosage_question = "dosage_question"
    clinical_protocol = "clinical_protocol"
    comparison_with_competitor = "comparison_with_competitor"
    safety_question = "safety_question"
    chitchat = "chitchat"
    out_of_scope = "out_of_scope"


class IntentClassification(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class GraphNodeTrace(BaseModel):
    """Una entrada del trace por nodo atravesado."""

    node: str
    latency_ms: int
    outcome: str | None = None
    payload: dict | None = None


class ConversationStateRecord(BaseModel):
    conversation_id: UUID
    current_product_id: UUID | None = None
    current_topic: str | None = None
    current_species: str | None = None
    last_intent: str | None = None
    updated_at: datetime | None = None
