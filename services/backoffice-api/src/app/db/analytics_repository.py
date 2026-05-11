"""Consultas agregadas para los endpoints de analytics."""

from __future__ import annotations

from biomont_common.db.pool import DatabasePool


class AnalyticsRepository:
    def __init__(self, pool: DatabasePool) -> None:
        self._pool = pool

    async def overview(self) -> dict:
        async with self._pool.acquire() as conn:
            metrics = await conn.fetchrow(
                """
                SELECT
                    (SELECT count(*) FROM public.conversations) AS total_conversations,
                    (SELECT count(*) FROM public.messages WHERE role = 'user') AS total_messages,
                    (SELECT count(*) FROM public.agent_decisions WHERE decision = 'answered')
                        AS total_answered,
                    (SELECT count(*) FROM public.agent_decisions WHERE decision = 'no_match')
                        AS total_no_match,
                    COALESCE(
                        (SELECT avg(latency_ms) FROM public.messages WHERE role = 'assistant'),
                        0
                    ) AS avg_latency_ms
                """
            )
            by_country = await conn.fetch(
                """
                SELECT d.country_iso, count(*) AS total
                FROM public.agent_decisions ad
                JOIN public.messages m ON m.id = ad.message_id
                LEFT JOIN LATERAL jsonb_array_elements(ad.retrieved) elem ON true
                LEFT JOIN public.documents d
                    ON d.id = (elem->>'document_id')::uuid
                WHERE ad.decision = 'answered'
                GROUP BY d.country_iso
                ORDER BY total DESC
                """
            )
            top_products = await conn.fetch(
                """
                SELECT d.product_name, count(*) AS total
                FROM public.agent_decisions ad
                CROSS JOIN LATERAL jsonb_array_elements(ad.retrieved) elem
                JOIN public.documents d
                    ON d.id = (elem->>'document_id')::uuid
                WHERE ad.decision = 'answered' AND d.product_name IS NOT NULL
                GROUP BY d.product_name
                ORDER BY total DESC
                LIMIT 10
                """
            )

        return {
            "total_conversations": int(metrics["total_conversations"] or 0),
            "total_messages": int(metrics["total_messages"] or 0),
            "total_answered": int(metrics["total_answered"] or 0),
            "total_no_match": int(metrics["total_no_match"] or 0),
            "avg_latency_ms": float(metrics["avg_latency_ms"] or 0.0),
            "by_country": [
                {"country_iso": row["country_iso"], "total": int(row["total"])}
                for row in by_country
            ],
            "top_products": [
                {"product_name": row["product_name"], "total": int(row["total"])}
                for row in top_products
            ],
        }
