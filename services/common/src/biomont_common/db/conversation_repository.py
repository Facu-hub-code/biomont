"""Persistencia de conversaciones, mensajes, decisiones y tickets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class StoredMessage:
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    citations: list[dict[str, Any]]


class ConversationRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get_or_create_active_conversation(
        self,
        rtc_user_id: UUID,
        inactivity_minutes: int = 60,
    ) -> UUID:
        """Devuelve la conversacion activa para el RTC, creandola si no existe.

        Se considera activa si tuvo un mensaje en los ultimos
        `inactivity_minutes` minutos.
        """

        async with self._pool.transaction() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM public.conversations
                WHERE rtc_user_id = $1
                  AND last_message_at > now() - ($2::int * interval '1 minute')
                ORDER BY last_message_at DESC
                LIMIT 1
                """,
                rtc_user_id,
                inactivity_minutes,
            )
            if row is not None:
                return row["id"]

            row = await conn.fetchrow(
                """
                INSERT INTO public.conversations (rtc_user_id)
                VALUES ($1)
                RETURNING id
                """,
                rtc_user_id,
            )
            return row["id"]

    async def insert_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: Iterable[dict[str, Any]] | None = None,
        model: str | None = None,
        latency_ms: int | None = None,
    ) -> UUID:
        citations_json = json.dumps(list(citations or []))
        async with self._pool.transaction() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.messages
                    (conversation_id, role, content, model, citations, latency_ms)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                RETURNING id
                """,
                conversation_id,
                role,
                content,
                model,
                citations_json,
                latency_ms,
            )
            await conn.execute(
                "UPDATE public.conversations SET last_message_at = now() WHERE id = $1",
                conversation_id,
            )
            return row["id"]

    async def insert_decision(
        self,
        *,
        message_id: UUID | None,
        decision: str,
        reasoning: str | None,
        retrieved: list[dict[str, Any]],
        top_similarity: float | None,
        system_prompt_version: int | None,
        graph_trace: list[dict[str, Any]] | None = None,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.agent_decisions
                    (message_id, decision, reasoning, retrieved,
                     top_similarity, system_prompt_version, graph_trace)
                VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::jsonb)
                RETURNING id
                """,
                message_id,
                decision,
                reasoning,
                json.dumps(retrieved),
                top_similarity,
                system_prompt_version,
                json.dumps(graph_trace or []),
            )
            return row["id"]

    async def insert_ticket(
        self,
        *,
        conversation_id: UUID | None,
        message_id: UUID | None,
        ticket_type: str,
        summary: str,
        notes: str | None = None,
    ) -> UUID:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.tickets
                    (conversation_id, message_id, type, summary, notes)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                conversation_id,
                message_id,
                ticket_type,
                summary,
                notes,
            )
            return row["id"]
