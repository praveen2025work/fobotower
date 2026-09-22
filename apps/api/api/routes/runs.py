"""Run schedule and regional rollups.

Static in Phase 1: these are the mock's seven recs across three regions and
four run windows. Phase 2 drives them from real investigation sessions.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["runs"])

RUN_WINDOWS = ["11:00", "15:00", "17:00", "19:00"]

REGIONS = [
    {
        "region": "APAC",
        "recs": [
            {
                "rec_id": "R-1050",
                "name": "CATS vs MOTIF — Rates",
                "scheduled": "11:00",
                "status": "cleared",
                "books_open": 22,
                "books_total": 22,
                "adj_pending": 0,
            },
            {
                "rec_id": "R-1055",
                "name": "Rec Factory — Cash Recon",
                "scheduled": "11:00",
                "status": "awaiting",
                "books_open": 9,
                "books_total": 11,
                "adj_pending": 14,
            },
            {
                "rec_id": "R-1060",
                "name": "CATS vs MOTIF — FX",
                "scheduled": "19:00",
                "status": "scheduled",
                "books_open": 0,
                "books_total": 15,
                "adj_pending": 0,
            },
        ],
    },
    {
        "region": "EMEA",
        "recs": [
            {
                "rec_id": "R-2010",
                "name": "CATS vs MOTIF — Credit",
                "scheduled": "15:00",
                "status": "in_progress",
                "books_open": 11,
                "books_total": 19,
                "adj_pending": 0,
            },
            {
                "rec_id": "R-2015",
                "name": "Rec Factory — Collateral",
                "scheduled": "15:00",
                "status": "blocked",
                "books_open": 1,
                "books_total": 7,
                "adj_pending": 0,
            },
        ],
    },
    {
        "region": "AMER",
        "recs": [
            {
                "rec_id": "R-3010",
                "name": "CATS vs MOTIF — Equities",
                "scheduled": "17:00",
                "status": "scheduled",
                "books_open": 0,
                "books_total": 41,
                "adj_pending": 0,
            },
            {
                "rec_id": "R-3015",
                "name": "Rec Factory — Cash Recon",
                "scheduled": "17:00",
                "status": "cleared",
                "books_open": 13,
                "books_total": 13,
                "adj_pending": 0,
            },
        ],
    },
]

# The session the console opens by default: R-1055, the case the mock shows.
DEFAULT_SESSION_ID = "sess-r1055"
DEFAULT_REC_ID = "R-1055"


def _stats() -> dict:
    recs = [r for region in REGIONS for r in region["recs"]]
    return {
        "recs": len(recs),
        "cleared": sum(1 for r in recs if r["status"] == "cleared"),
        "awaiting": sum(1 for r in recs if r["status"] == "awaiting"),
        "blocked": sum(1 for r in recs if r["status"] == "blocked"),
        "adj_pending": sum(r["adj_pending"] for r in recs),
        "auto_posted": 32,
        "books_open": sum(r["books_open"] for r in recs),
        "books_not_open": sum(r["books_total"] - r["books_open"] for r in recs),
        "unlocked": 53,
        "unlocked_total": 160,
        "now": "17:40",
        "next_run": "19:00",
        "timezone": "IST",
        "business_date": "2026-08-03",
    }


@router.get("/runs")
async def get_runs() -> dict:
    return {
        "regions": REGIONS,
        "run_windows": RUN_WINDOWS,
        "stats": _stats(),
        "default_rec_id": DEFAULT_REC_ID,
        "default_session_id": DEFAULT_SESSION_ID,
    }
