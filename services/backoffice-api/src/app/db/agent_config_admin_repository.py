"""Repositorio BO para agent_config_versions + agent_intent_config (spec 008)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.agent_config_repository import VALID_DOCUMENT_KINDS
from biomont_common.db.pool import DatabasePool
from biomont_common.schemas.agent_graph import Intent


@dataclass(slots=True)
class AgentIntentConfigRow:
    id: UUID
    config_version_id: UUID
    intent_slug: str
    display_label: str
    classifier_hint: str
    document_kinds: list[str]
    sort_order: int
    is_enabled: bool


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
    intents: list[AgentIntentConfigRow]


def _validate_kinds(kinds: list[str]) -> None:
    invalid = [k for k in kinds if k not in VALID_DOCUMENT_KINDS]
    if invalid:
        raise ValueError(f"document_kinds invalidos: {invalid}")


def _validate_slugs(slugs: list[str]) -> None:
    allowed = {i.value for i in Intent}
    invalid = [s for s in slugs if s not in allowed]
    if invalid:
        raise ValueError(f"intent_slug invalidos: {invalid}")


class AgentConfigAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_versions(self) -> list[AgentConfigVersionRow]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT v.*,
                       COALESCE(
                           json_agg(
                               json_build_object(
                                   'id', i.id,
                                   'config_version_id', i.config_version_id,
                                   'intent_slug', i.intent_slug,
                                   'display_label', i.display_label,
                                   'classifier_hint', i.classifier_hint,
                                   'document_kinds', i.document_kinds,
                                   'sort_order', i.sort_order,
                                   'is_enabled', i.is_enabled
                               )
                               ORDER BY i.sort_order, i.intent_slug
                           ) FILTER (WHERE i.id IS NOT NULL),
                           '[]'
                       ) AS intents_json
                FROM public.agent_config_versions v
                LEFT JOIN public.agent_intent_config i ON i.config_version_id = v.id
                GROUP BY v.id
                ORDER BY v.version DESC
                """
            )
        return [_version_from_row(r) for r in rows]

    async def get_active(self) -> AgentConfigVersionRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT v.*,
                       COALESCE(
                           json_agg(
                               json_build_object(
                                   'id', i.id,
                                   'config_version_id', i.config_version_id,
                                   'intent_slug', i.intent_slug,
                                   'display_label', i.display_label,
                                   'classifier_hint', i.classifier_hint,
                                   'document_kinds', i.document_kinds,
                                   'sort_order', i.sort_order,
                                   'is_enabled', i.is_enabled
                               )
                               ORDER BY i.sort_order, i.intent_slug
                           ) FILTER (WHERE i.id IS NOT NULL),
                           '[]'
                       ) AS intents_json
                FROM public.agent_config_versions v
                LEFT JOIN public.agent_intent_config i ON i.config_version_id = v.id
                WHERE v.is_active = true
                GROUP BY v.id
                LIMIT 1
                """
            )
        return _version_from_row(row) if row else None

    async def create_version(
        self,
        *,
        top_k: int,
        candidate_k: int,
        full_corpus_for_all_intents: bool,
        classifier_preamble: str | None,
        intents: list[dict],
        created_by: UUID,
        activate: bool = True,
    ) -> AgentConfigVersionRow:
        if top_k > candidate_k:
            raise ValueError("top_k no puede ser mayor que candidate_k")
        slugs = [i["intent_slug"] for i in intents]
        _validate_slugs(slugs)
        for item in intents:
            _validate_kinds(list(item.get("document_kinds") or []))

        async with self._pool.transaction() as conn:
            next_row = await conn.fetchrow(
                "SELECT COALESCE(max(version), 0) + 1 AS next FROM public.agent_config_versions"
            )
            next_version = int(next_row["next"])

            if activate:
                await conn.execute(
                    "UPDATE public.agent_config_versions SET is_active = false "
                    "WHERE is_active = true"
                )

            version_row = await conn.fetchrow(
                """
                INSERT INTO public.agent_config_versions (
                    version, is_active, top_k, candidate_k,
                    full_corpus_for_all_intents, classifier_preamble, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
                """,
                next_version,
                activate,
                top_k,
                candidate_k,
                full_corpus_for_all_intents,
                classifier_preamble,
                created_by,
            )
            version_id = version_row["id"]

            intent_rows: list[AgentIntentConfigRow] = []
            for item in intents:
                ir = await conn.fetchrow(
                    """
                    INSERT INTO public.agent_intent_config (
                        config_version_id, intent_slug, display_label, classifier_hint,
                        document_kinds, sort_order, is_enabled
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    version_id,
                    item["intent_slug"],
                    item["display_label"],
                    item["classifier_hint"],
                    list(item.get("document_kinds") or []),
                    int(item.get("sort_order") or 0),
                    bool(item.get("is_enabled", True)),
                )
                intent_rows.append(_intent_from_row(ir))

        return AgentConfigVersionRow(
            id=version_row["id"],
            version=int(version_row["version"]),
            is_active=bool(version_row["is_active"]),
            top_k=int(version_row["top_k"]),
            candidate_k=int(version_row["candidate_k"]),
            full_corpus_for_all_intents=bool(
                version_row["full_corpus_for_all_intents"]
            ),
            classifier_preamble=version_row["classifier_preamble"],
            created_by=version_row["created_by"],
            created_at=version_row["created_at"],
            intents=intent_rows,
        )

    async def activate_version(self, version: int) -> AgentConfigVersionRow | None:
        async with self._pool.transaction() as conn:
            await conn.execute(
                "UPDATE public.agent_config_versions SET is_active = false "
                "WHERE is_active = true"
            )
            row = await conn.fetchrow(
                "UPDATE public.agent_config_versions SET is_active = true "
                "WHERE version = $1 RETURNING id",
                version,
            )
            if row is None:
                return None
            full = await conn.fetchrow(
                """
                SELECT v.*,
                       COALESCE(
                           json_agg(
                               json_build_object(
                                   'id', i.id,
                                   'config_version_id', i.config_version_id,
                                   'intent_slug', i.intent_slug,
                                   'display_label', i.display_label,
                                   'classifier_hint', i.classifier_hint,
                                   'document_kinds', i.document_kinds,
                                   'sort_order', i.sort_order,
                                   'is_enabled', i.is_enabled
                               )
                               ORDER BY i.sort_order, i.intent_slug
                           ) FILTER (WHERE i.id IS NOT NULL),
                           '[]'
                       ) AS intents_json
                FROM public.agent_config_versions v
                LEFT JOIN public.agent_intent_config i ON i.config_version_id = v.id
                WHERE v.version = $1
                GROUP BY v.id
                """,
                version,
            )
        return _version_from_row(full) if full else None


def _intent_from_row(row) -> AgentIntentConfigRow:
    return AgentIntentConfigRow(
        id=row["id"],
        config_version_id=row["config_version_id"],
        intent_slug=row["intent_slug"],
        display_label=row["display_label"],
        classifier_hint=row["classifier_hint"],
        document_kinds=list(row["document_kinds"] or []),
        sort_order=int(row["sort_order"]),
        is_enabled=bool(row["is_enabled"]),
    )


def _version_from_row(row) -> AgentConfigVersionRow:
    import json

    raw = row["intents_json"]
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw or []
    intents = [
        AgentIntentConfigRow(
            id=UUID(item["id"]) if isinstance(item["id"], str) else item["id"],
            config_version_id=(
                UUID(item["config_version_id"])
                if isinstance(item["config_version_id"], str)
                else item["config_version_id"]
            ),
            intent_slug=item["intent_slug"],
            display_label=item["display_label"],
            classifier_hint=item["classifier_hint"],
            document_kinds=list(item["document_kinds"] or []),
            sort_order=int(item["sort_order"]),
            is_enabled=bool(item["is_enabled"]),
        )
        for item in parsed
        if item.get("id")
    ]
    return AgentConfigVersionRow(
        id=row["id"],
        version=int(row["version"]),
        is_active=bool(row["is_active"]),
        top_k=int(row["top_k"]),
        candidate_k=int(row["candidate_k"]),
        full_corpus_for_all_intents=bool(row["full_corpus_for_all_intents"]),
        classifier_preamble=row["classifier_preamble"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        intents=intents,
    )
