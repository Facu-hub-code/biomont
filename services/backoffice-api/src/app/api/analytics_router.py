"""Endpoint de analytics minimo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_analytics, require_roles
from app.db.analytics_repository import AnalyticsRepository
from app.schemas.analytics import AnalyticsOverview
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    analytics: Annotated[AnalyticsRepository, Depends(get_analytics)],
    _: Annotated[CurrentUser, Depends(require_roles("admin", "scientist", "viewer"))],
) -> AnalyticsOverview:
    data = await analytics.overview()
    return AnalyticsOverview(**data)
