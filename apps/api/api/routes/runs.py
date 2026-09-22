"""Run schedule and regional rollups.

Phase 1 served this from a static Python dict. Every field now comes from
app/queries/schedule.py, which reads rows.
"""

from datetime import date

from fastapi import APIRouter

from api.deps import ensure_fixtures
from app.db.base import get_session
from app.queries.schedule import header_stats, regions_with_recs, run_windows

router = APIRouter(prefix="/api", tags=["runs"])

# The business date the fixtures cover. Real deployments take this from the
# request or the calendar; here it pins the demo to the mock's COB.
DEFAULT_BUSINESS_DATE = date(2026, 8, 3)

# The case the console opens by default: R-1055, the one the mock shows.
DEFAULT_REC_ID = "R-1055"
DEFAULT_SESSION_ID = "sess-r1055"


@router.get("/runs")
async def get_runs(business_date: date = DEFAULT_BUSINESS_DATE) -> dict:
    async with get_session() as s:
        await ensure_fixtures(s)
        return {
            "regions": await regions_with_recs(s, business_date),
            "run_windows": await run_windows(s, business_date),
            "stats": await header_stats(s, business_date),
            "default_rec_id": DEFAULT_REC_ID,
            "default_session_id": DEFAULT_SESSION_ID,
        }
