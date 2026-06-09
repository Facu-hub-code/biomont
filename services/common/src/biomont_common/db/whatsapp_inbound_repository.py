"""Dedupe de mensajes entrantes WhatsApp por provider_message_id (wamid)."""

from __future__ import annotations

from biomont_common.db.pool import DatabasePool


class WhatsappInboundRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def try_claim(
        self,
        *,
        provider_message_id: str,
        from_phone_e164: str,
        message_type: str,
    ) -> bool:
        """True si este wamid no fue visto antes (insert atomico)."""

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.whatsapp_inbound_messages (
                    provider_message_id, from_phone_e164, message_type, status
                ) VALUES ($1, $2, $3, 'pending')
                ON CONFLICT (provider_message_id) DO NOTHING
                RETURNING provider_message_id
                """,
                provider_message_id,
                from_phone_e164,
                message_type,
            )
        return row is not None

    async def mark_processed(self, provider_message_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.whatsapp_inbound_messages
                SET status = 'processed', processed_at = now()
                WHERE provider_message_id = $1
                """,
                provider_message_id,
            )
