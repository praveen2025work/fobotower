"""Agent analytics."""

from datetime import date

from fastapi import APIRouter

from api.deps import ensure_fixtures
from app.db.base import get_session
from app.queries.analytics import analytics_summary
from fixtures.history import COB

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics")
async def get_analytics(business_date: date = COB) -> dict:
    async with get_session() as s:
        await ensure_fixtures(s)
        return await analytics_summary(s, business_date)
