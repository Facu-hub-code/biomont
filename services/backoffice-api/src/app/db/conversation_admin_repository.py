"""Lectura de conversaciones y mensajes para el backoffice (espejo)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from biomont_common.db.pool import DatabasePool


@dataclass(slots=True)
class ConversationListRow:
    id: UUID
    rtc_user_id: UUID
    rtc_name: str
    phone_e164: str
    started_at: datetime
    last_message_at: datetime
    last_preview: str | None


@dataclass(slots=True)
class ConversationMessageRow:
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class ConversationAdminRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def list_conversations(self, *, limit: int = 200) -> list[ConversationListRow]:
        cap = min(max(limit, 1), 500)
        query = """
            SELECT c.id, c.rtc_user_id, c.started_at, c.last_message_at,
                   u.name AS rtc_name, u.phone_e164,
                   lm.preview AS last_preview
            FROM public.conversations c
            JOIN public.rtc_users u ON u.id = c.rtc_user_id
            LEFT JOIN LATERAL (
                SELECT m.content AS preview
                FROM public.messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.created_at DESC
                LIMIT 1
            ) lm ON true
            ORDER BY c.last_message_at DESC
            LIMIT $1
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, cap)
        return [
            ConversationListRow(
                id=row["id"],
                rtc_user_id=row["rtc_user_id"],
                rtc_name=row["rtc_name"],
                phone_e164=row["phone_e164"],
                started_at=row["started_at"],
                last_message_at=row["last_message_at"],
                last_preview=row["last_preview"],
            )
            for row in rows
        ]

    async def list_messages(
        self, conversation_id: UUID, *, limit: int = 500
    ) -> list[ConversationMessageRow]:
        cap = min(max(limit, 1), 2000)
        query = """
            SELECT m.id, m.conversation_id, m.role::text AS role,
                   m.content, m.created_at
            FROM public.messages m
            JOIN public.conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = $1
            ORDER BY m.created_at ASC, m.id ASC
            LIMIT $2
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, conversation_id, cap)
        return [
            ConversationMessageRow(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
