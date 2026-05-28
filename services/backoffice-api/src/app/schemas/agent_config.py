"""Schemas API para configuracion del agente (spec 008)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from biomont_common.db.agent_config_repository import VALID_DOCUMENT_KINDS
from biomont_common.schemas.agent_graph import Intent


class IntentConfigIn(BaseModel):
    intent_slug: str
    display_label: str = Field(min_length=1, max_length=120)
    classifier_hint: str = Field(min_length=1, max_length=2000)
    document_kinds: list[str] = Field(default_factory=list)
    sort_order: int = 0
    is_enabled: bool = True

    @field_validator("intent_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        allowed = {i.value for i in Intent}
        if v not in allowed:
            raise ValueError(f"intent_slug debe ser uno de: {sorted(allowed)}")
        return v

    @field_validator("document_kinds")
    @classmethod
    def validate_kinds(cls, v: list[str]) -> list[str]:
        invalid = [k for k in v if k not in VALID_DOCUMENT_KINDS]
        if invalid:
            raise ValueError(f"document_kinds invalidos: {invalid}")
        return v


class AgentConfigVersionCreate(BaseModel):
    top_k: int = Field(ge=1, le=20, default=6)
    candidate_k: int = Field(ge=5, le=100, default=25)
    full_corpus_for_all_intents: bool = False
    classifier_preamble: str | None = None
    intents: list[IntentConfigIn]
    activate: bool = True

    @field_validator("candidate_k")
    @classmethod
    def top_k_le_candidate(cls, v: int, info) -> int:
        top_k = info.data.get("top_k", 6)
        if top_k > v:
            raise ValueError("top_k no puede ser mayor que candidate_k")
        return v


class IntentConfigOut(BaseModel):
    id: UUID
    intent_slug: str
    display_label: str
    classifier_hint: str
    document_kinds: list[str]
    sort_order: int
    is_enabled: bool


class AgentConfigVersionOut(BaseModel):
    id: UUID
    version: int
    is_active: bool
    top_k: int
    candidate_k: int
    full_corpus_for_all_intents: bool
    classifier_preamble: str | None
    created_at: datetime
    intents: list[IntentConfigOut] = Field(default_factory=list)
