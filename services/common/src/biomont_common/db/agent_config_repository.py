"""Configuracion activa del agente (spec 008): retrieval + intents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from biomont_common.agent_config_prompt import (
    IntentPromptLine,
    build_classifier_system_prompt,
)
from biomont_common.db.pool import DatabasePool
from biomont_common.logging import get_logger
from biomont_common.schemas.agent_graph import Intent
from biomont_common.schemas.knowledge import DocumentKind
from biomont_common.settings import RagSettings

_logger = get_logger("agent_config")

VALID_DOCUMENT_KINDS = frozenset({k.value for k in DocumentKind})

# Fallback cuando no hay fila activa en DB (alineado a meta_filter.py pre-008).
_LEGACY_INTENT_KINDS: dict[str, list[str] | None] = {
    Intent.dose_calculation.value: [],
    Intent.clinical_protocol.value: ["bitacora", "balotario"],
    Intent.dosage_question.value: ["bitacora", "ficha_tecnica", "balotario"],
    Intent.safety_question.value: ["ficha_tecnica", "bitacora", "balotario"],
    Intent.comparison_with_competitor.value: ["bitacora", "comparativo_comercial"],
}


@dataclass(frozen=True, slots=True)
class IntentConfigEntry:
    intent_slug: str
    display_label: str
    classifier_hint: str
    document_kinds: tuple[str, ...]
    sort_order: int
    is_enabled: bool


@dataclass(frozen=True, slots=True)
class ActiveAgentConfig:
    version: int
    top_k: int
    candidate_k: int
    full_corpus_for_all_intents: bool
    classifier_system_prompt: str
    cache_namespace: str
    intent_kinds_by_slug: dict[str, list[str] | None]
    intents: tuple[IntentConfigEntry, ...] = field(default_factory=tuple)


def _kinds_from_db_array(raw: list[str] | None) -> list[str] | None:
    if not raw:
        return None
    return list(raw)


def snapshot_from_rag_settings(settings: RagSettings) -> ActiveAgentConfig:
    """Fallback env/codigo cuando no hay config activa en Postgres."""

    lines = [
        IntentPromptLine(
            intent_slug=Intent.dosage_question.value,
            classifier_hint=(
                "dosis, cuanto administrar, presentaciones, via o modo de administracion, "
                "indicacion o indicaciones terapeuticas/de uso."
            ),
            is_enabled=True,
            sort_order=10,
        ),
        IntentPromptLine(
            intent_slug=Intent.clinical_protocol.value,
            classifier_hint="protocolo terapeutico nombrado o esquema de tratamiento.",
            is_enabled=True,
            sort_order=20,
        ),
        IntentPromptLine(
            intent_slug=Intent.comparison_with_competitor.value,
            classifier_hint="comparacion con otro producto.",
            is_enabled=True,
            sort_order=30,
        ),
        IntentPromptLine(
            intent_slug=Intent.safety_question.value,
            classifier_hint="efectos adversos, contraindicaciones, toxicidad, gestacion.",
            is_enabled=True,
            sort_order=40,
        ),
        IntentPromptLine(
            intent_slug=Intent.chitchat.value,
            classifier_hint="saludo o conversacion casual sin consulta clinica.",
            is_enabled=True,
            sort_order=50,
        ),
        IntentPromptLine(
            intent_slug=Intent.out_of_scope.value,
            classifier_hint="temas ajenos al dominio veterinario-farmaceutico.",
            is_enabled=True,
            sort_order=60,
        ),
    ]
    prompt = build_classifier_system_prompt(preamble=None, intents=lines)
    return ActiveAgentConfig(
        version=0,
        top_k=settings.top_k,
        candidate_k=settings.candidate_k,
        full_corpus_for_all_intents=settings.full_corpus_for_all_intents,
        classifier_system_prompt=prompt,
        cache_namespace="env-fallback",
        intent_kinds_by_slug=dict(_LEGACY_INTENT_KINDS),
        intents=(),
    )


class AgentConfigRepository:
    def __init__(self, pool: DatabasePool, cache_ttl_seconds: int = 60) -> None:
        self._pool = pool
        self._cache_ttl = cache_ttl_seconds
        self._cached_at: float = 0.0
        self._cached: ActiveAgentConfig | None = None

    async def get_active(
        self, *, rag_fallback: RagSettings | None = None
    ) -> ActiveAgentConfig:
        now = time.monotonic()
        if self._cached is not None and (now - self._cached_at) < self._cache_ttl:
            _logger.debug("agent_config_cache_hit", action="cache_hit")
            return self._cached

        _logger.debug("agent_config_cache_miss", action="cache_miss")
        async with self._pool.acquire() as conn:
            version_row = await conn.fetchrow(
                """
                SELECT id, version, top_k, candidate_k, full_corpus_for_all_intents,
                       classifier_preamble
                FROM public.agent_config_versions
                WHERE is_active = true
                LIMIT 1
                """
            )
            if version_row is None:
                from biomont_common.settings import get_rag_settings

                cfg = snapshot_from_rag_settings(rag_fallback or get_rag_settings())
                self._store_cache(cfg)
                return cfg

            intent_rows = await conn.fetch(
                """
                SELECT intent_slug, display_label, classifier_hint, document_kinds,
                       sort_order, is_enabled
                FROM public.agent_intent_config
                WHERE config_version_id = $1
                ORDER BY sort_order, intent_slug
                """,
                version_row["id"],
            )

        entries: list[IntentConfigEntry] = []
        prompt_lines: list[IntentPromptLine] = []
        kinds_map: dict[str, list[str] | None] = {}

        for row in intent_rows:
            kinds_raw = list(row["document_kinds"] or [])
            kinds_map[row["intent_slug"]] = _kinds_from_db_array(kinds_raw)
            entry = IntentConfigEntry(
                intent_slug=row["intent_slug"],
                display_label=row["display_label"],
                classifier_hint=row["classifier_hint"],
                document_kinds=tuple(kinds_raw),
                sort_order=int(row["sort_order"]),
                is_enabled=bool(row["is_enabled"]),
            )
            entries.append(entry)
            prompt_lines.append(
                IntentPromptLine(
                    intent_slug=entry.intent_slug,
                    classifier_hint=entry.classifier_hint,
                    is_enabled=entry.is_enabled,
                    sort_order=entry.sort_order,
                )
            )

        version = int(version_row["version"])
        prompt = build_classifier_system_prompt(
            preamble=version_row["classifier_preamble"],
            intents=prompt_lines,
        )
        cfg = ActiveAgentConfig(
            version=version,
            top_k=int(version_row["top_k"]),
            candidate_k=int(version_row["candidate_k"]),
            full_corpus_for_all_intents=bool(
                version_row["full_corpus_for_all_intents"]
            ),
            classifier_system_prompt=prompt,
            cache_namespace=f"db-v{version}",
            intent_kinds_by_slug=kinds_map,
            intents=tuple(entries),
        )
        _logger.info(
            "agent_config_loaded",
            action="loaded",
            config_version=version,
            top_k=cfg.top_k,
            intent_count=len(entries),
            full_corpus=cfg.full_corpus_for_all_intents,
        )
        self._store_cache(cfg)
        return cfg

    def _store_cache(self, cfg: ActiveAgentConfig) -> None:
        self._cached = cfg
        self._cached_at = time.monotonic()

    def invalidate(self) -> None:
        self._cached_at = 0.0
        self._cached = None


@dataclass(slots=True)
class AgentConfigVersionRow:
    id: UUID
    version: int
    is_active: bool
    top_k: int
    candidate_k: int
    full_corpus_for_all_intents: bool
    classifier_preamble: str | None
    created_by: UUID | None
    created_at: datetime
