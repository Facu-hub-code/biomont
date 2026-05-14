"""Consultas de auditoria sobre `agent_decisions` para backoffice."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class AgentDecisionListRow:
    id: UUID
    message_id: UUID | None
    decision: str
    reasoning: str | None
    top_similarity: float | None
    system_prompt_version: int | None
    created_at: datetime
    conversation_id: UUID | None
    rtc_user_id: UUID | None
    rtc_name: str | None
    phone_e164: str | None
    message_preview: str | None


@dataclass(slots=True)
class AgentDecisionDetailRow:
    id: UUID
    message_id: UUID | None
    decision: str
    reasoning: str | None
    retrieved: list[dict[str, Any]]
    top_similarity: float | None
    system_prompt_version: int | None
    graph_trace: list[dict[str, Any]]
    created_at: datetime
    message_content: str | None
    message_role: str | None
    conversation_id: UUID | None
    conversation_started_at: datetime | None
    rtc_user_id: UUID | None
    rtc_name: str | None
    phone_e164: str | None
    previous_user_message: str | None


class AgentDecisionRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_decisions(
        self,
        *,
        page: int,
        page_size: int,
        decision: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        phone_digits: str | None = None,
        conversation_id: UUID | None = None,
    ) -> tuple[int, list[AgentDecisionListRow]]:
        offset = (page - 1) * page_size
        where_clause = """
            WHERE ($1::text IS NULL OR ad.decision::text = $1)
              AND ($2::timestamptz IS NULL OR ad.created_at >= $2)
              AND ($3::timestamptz IS NULL OR ad.created_at <= $3)
              AND ($4::uuid IS NULL OR c.id = $4)
              AND (
                    $5::text IS NULL
                    OR regexp_replace(COALESCE(u.phone_e164, ''), '[^0-9]', '', 'g')
                       LIKE '%' || $5 || '%'
              )
        """
        count_sql = f"""
            SELECT count(*)
            FROM public.agent_decisions ad
            LEFT JOIN public.messages m ON m.id = ad.message_id
            LEFT JOIN public.conversations c ON c.id = m.conversation_id
            LEFT JOIN public.rtc_users u ON u.id = c.rtc_user_id
            {where_clause}
        """
        list_sql = f"""
            SELECT
                ad.id,
                ad.message_id,
                ad.decision::text AS decision,
                ad.reasoning,
                ad.top_similarity,
                ad.system_prompt_version,
                ad.created_at,
                c.id AS conversation_id,
                u.id AS rtc_user_id,
                u.name AS rtc_name,
                u.phone_e164,
                LEFT(m.content, 240) AS message_preview
            FROM public.agent_decisions ad
            LEFT JOIN public.messages m ON m.id = ad.message_id
            LEFT JOIN public.conversations c ON c.id = m.conversation_id
            LEFT JOIN public.rtc_users u ON u.id = c.rtc_user_id
            {where_clause}
            ORDER BY ad.created_at DESC
            LIMIT $6 OFFSET $7
        """
        async with self._pool.acquire() as conn:
            total = int(
                await conn.fetchval(
                    count_sql,
                    decision,
                    date_from,
                    date_to,
                    conversation_id,
                    phone_digits,
                )
                or 0
            )
            rows = await conn.fetch(
                list_sql,
                decision,
                date_from,
                date_to,
                conversation_id,
                phone_digits,
                page_size,
                offset,
            )
        return total, [self._row_to_list_item(row) for row in rows]

    async def get_decision(
        self,
        decision_id: UUID,
    ) -> AgentDecisionDetailRow | None:
        sql = """
            SELECT
                ad.id,
                ad.message_id,
                ad.decision::text AS decision,
                ad.reasoning,
                ad.retrieved,
                ad.top_similarity,
                ad.system_prompt_version,
                ad.graph_trace,
                ad.created_at,
                m.content AS message_content,
                m.role::text AS message_role,
                c.id AS conversation_id,
                c.started_at AS conversation_started_at,
                u.id AS rtc_user_id,
                u.name AS rtc_name,
                u.phone_e164,
                prev_user.content AS previous_user_message
            FROM public.agent_decisions ad
            LEFT JOIN public.messages m ON m.id = ad.message_id
            LEFT JOIN public.conversations c ON c.id = m.conversation_id
            LEFT JOIN public.rtc_users u ON u.id = c.rtc_user_id
            LEFT JOIN LATERAL (
                SELECT m2.content
                FROM public.messages m2
                WHERE m2.conversation_id = c.id
                  AND m2.role = 'user'
                  AND (
                    m.created_at IS NULL
                    OR m2.created_at <= m.created_at
                  )
                ORDER BY m2.created_at DESC
                LIMIT 1
            ) prev_user ON true
            WHERE ad.id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, decision_id)
        return self._row_to_detail_item(row) if row else None

    @staticmethod
    def _parse_json(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            parsed = json.loads(value)
            return parsed
        return default

    def _row_to_list_item(self, row: Any) -> AgentDecisionListRow:
        return AgentDecisionListRow(
            id=row["id"],
            message_id=row["message_id"],
            decision=row["decision"],
            reasoning=row["reasoning"],
            top_similarity=(
                float(row["top_similarity"]) if row["top_similarity"] is not None else None
            ),
            system_prompt_version=row["system_prompt_version"],
            created_at=row["created_at"],
            conversation_id=row["conversation_id"],
            rtc_user_id=row["rtc_user_id"],
            rtc_name=row["rtc_name"],
            phone_e164=row["phone_e164"],
            message_preview=row["message_preview"],
        )

    def _row_to_detail_item(self, row: Any) -> AgentDecisionDetailRow:
        return AgentDecisionDetailRow(
            id=row["id"],
            message_id=row["message_id"],
            decision=row["decision"],
            reasoning=row["reasoning"],
            retrieved=self._parse_json(row["retrieved"], []),
            top_similarity=(
                float(row["top_similarity"]) if row["top_similarity"] is not None else None
            ),
            system_prompt_version=row["system_prompt_version"],
            graph_trace=self._parse_json(row["graph_trace"], []),
            created_at=row["created_at"],
            message_content=row["message_content"],
            message_role=row["message_role"],
            conversation_id=row["conversation_id"],
            conversation_started_at=row["conversation_started_at"],
            rtc_user_id=row["rtc_user_id"],
            rtc_name=row["rtc_name"],
            phone_e164=row["phone_e164"],
            previous_user_message=row["previous_user_message"],
        )
