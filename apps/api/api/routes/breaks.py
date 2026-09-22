"""Break population within a session, paged.

Paging is bounded and reports whether it truncated, so a caller always knows
what it did not receive.
"""

from fastapi import APIRouter

from api.routes.sessions import load_snapshot

router = APIRouter(prefix="/api", tags=["breaks"])

MAX_LIMIT = 100


@router.get("/breaks")
async def list_breaks(session_id: str, limit: int = 50, offset: int = 0) -> dict:
    snapshot = await load_snapshot(session_id)
    values = snapshot.values or {}
    breaks = values.get("breaks", [])
    deltas = values.get("deltas", {})

    bounded = min(limit, MAX_LIMIT)
    page = breaks[offset : offset + bounded]

    return {
        "breaks": [
            {
                "break_id": b["break_id"],
                "book_ref": b["book_ref"],
                "line_code": b.get("line_code", "CASH"),
                "delta": deltas.get(b["break_id"]),
            }
            for b in page
        ],
        "total": len(breaks),
        "offset": offset,
        "limit": bounded,
        "truncated": offset + bounded < len(breaks),
    }
