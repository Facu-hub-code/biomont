"""Estado conversacional (`conversation_state`, spec 003).

Memoria deterministica 1:1 con `conversations`, actualizada por el
nodo `StateUpdater` del grafo al final de cada turno.
"""

from __future__ import annotations

from uuid import UUID

from biomont_common.db.pool import DatabasePool
from biomont_common.schemas.agent_graph import ConversationStateRecord


class ConversationStateRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def get(self, conversation_id: UUID) -> ConversationStateRecord | None:
        query = """
            SELECT conversation_id, current_product_id, current_topic,
                   current_species, last_intent, updated_at
            FROM public.conversation_state
            WHERE conversation_id = $1
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, conversation_id)
        if row is None:
            return None
        return ConversationStateRecord(
            conversation_id=row["conversation_id"],
            current_product_id=row["current_product_id"],
            current_topic=row["current_topic"],
            current_species=row["current_species"],
            last_intent=row["last_intent"],
            updated_at=row["updated_at"],
        )

    async def upsert(
        self,
        *,
        conversation_id: UUID,
        current_product_id: UUID | None,
        current_topic: str | None,
        current_species: str | None,
        last_intent: str | None,
    ) -> None:
        """Idempotente. Si la fila no existe la crea, si existe la actualiza."""

        query = """
            INSERT INTO public.conversation_state
                (conversation_id, current_product_id, current_topic,
                 current_species, last_intent, updated_at)
            VALUES ($1, $2, $3, $4, $5, now())
            ON CONFLICT (conversation_id) DO UPDATE
                SET current_product_id = EXCLUDED.current_product_id,
                    current_topic      = EXCLUDED.current_topic,
                    current_species    = EXCLUDED.current_species,
                    last_intent        = EXCLUDED.last_intent,
                    updated_at         = now()
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                conversation_id,
                current_product_id,
                current_topic,
                current_species,
                last_intent,
            )
