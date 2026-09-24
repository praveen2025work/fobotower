"""The Human-in-Loop queue and the notification activity feed.

The queue spans every rec with work waiting, not just the one on screen:
its whole purpose is to tell a controller what is outstanding elsewhere.
"""

from datetime import date

from fastapi import APIRouter
from sqlalchemy import select

from api.deps import checkpointer, ensure_fixtures
from api.routes.recs import session_id_for
from app.db.base import get_session
from app.db.models_ops import Reconciliation, Run
from app.queries.activity import activity_feed
from app.workflow.graph import graph_for_session
from fixtures.history import COB

router = APIRouter(prefix="/api", tags=["worklist"])


@router.get("/activity")
async def get_activity(business_date: date = COB) -> dict:
    async with get_session() as s:
        await ensure_fixtures(s)
        return {"events": await activity_feed(s, business_date)}


@router.get("/worklist")
async def get_worklist(business_date: date = COB) -> dict:
    """Pattern groups awaiting sign-off, across every rec that has any."""
    async with get_session() as s:
        await ensure_fixtures(s)
        rows = (
            await s.execute(
                select(Reconciliation, Run)
                .join(Run, Run.rec_id == Reconciliation.rec_id)
                .where(Run.business_date == business_date)
                .order_by(Reconciliation.region, Reconciliation.rec_id)
            )
        ).all()

        items: list[dict] = []
        async with checkpointer() as cp:
            for rec, _run in rows:
                sid = session_id_for(rec.rec_id)
                graph, _pinned = await graph_for_session(cp, s, sid)
                snapshot = await graph.aget_state({"configurable": {"thread_id": sid}})
                v = snapshot.values
                if not v:
                    continue
                deltas = v.get("deltas", {})
                meta = v.get("group_meta", {})
                for g in v.get("pattern_groups", []):
                    items.append(
                        {
                            "group_id": g.group_id,
                            "rec_id": rec.rec_id,
                            "rec_name": rec.name,
                            "region": rec.region,
                            "pattern_code": g.pattern_code,
                            "label": g.label,
                            "mode": g.mode,
                            "book_count": len(g.break_ids),
                            "total": sum(deltas.get(b, 0.0) for b in g.break_ids),
                            "ungrounded_count": meta.get(g.group_id, {}).get(
                                "ungrounded_count", 0
                            ),
                            "carried_runs": meta.get(g.group_id, {}).get(
                                "carried_runs", 0
                            ),
                        }
                    )

    return {
        "pending": sum(i["book_count"] for i in items),
        "items": items,
    }
