from __future__ import annotations

from pydantic import BaseModel


class AnalyticsCountByCountry(BaseModel):
    country_iso: str | None
    total: int


class AnalyticsTopProduct(BaseModel):
    product_name: str
    total: int


class AnalyticsOverview(BaseModel):
    total_conversations: int
    total_messages: int
    total_answered: int
    total_no_match: int
    avg_latency_ms: float
    by_country: list[AnalyticsCountByCountry]
    top_products: list[AnalyticsTopProduct]
