"""Rec-scoped investigation.

The console navigates by rec, not by opaque session id: selecting a rec in
the rail must load that rec's case. A session id is derived from the rec so
the two stay in step.
"""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.auth import current_caller
from api.deps import checkpointer, ensure_fixtures
from api.routes.sessions import CAUSE_TO_SNAPSHOT, PIPELINE_STAGES
from app.db.base import get_session
from app.db.models_ops import Reconciliation, Run
from app.grounding.recorder import calls_for
from app.workflow.graph import build_graph, run_investigation
from fixtures.history import COB, breaks_for_rec

router = APIRouter(prefix="/api/recs", tags=["recs"])


def session_id_for(rec_id: str) -> str:
    return f"sess-{rec_id.lower()}"


async def _rec_and_run(s, rec_id: str, business_date: date):
    row = (
        await s.execute(
            select(Reconciliation, Run)
            .join(Run, Run.rec_id == Reconciliation.rec_id)
            .where(
                Reconciliation.rec_id == rec_id, Run.business_date == business_date
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no run for {rec_id}")
    return row


def _initial_state(rec, run, breaks: list[dict]) -> dict:
    return {
        "investigation_session_id": session_id_for(rec.rec_id),
        "reconciliation_id": rec.rec_id,
        "master_book": rec.master_book,
        "business_date": run.business_date,
        "run_id": run.run_id,
        "caller": current_caller(),
        "breaks": [b | CAUSE_TO_SNAPSHOT[b["cause"]] for b in breaks],
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }


def _header(rec, run) -> dict:
    return {
        "rec_id": rec.rec_id,
        "name": rec.name,
        "region": rec.region,
        "master_book": rec.master_book,
        "business_date": str(run.business_date),
        "run_id": run.run_id,
        "scheduled": run.scheduled_time.strftime("%H:%M"),
        "completed": run.completed_at.strftime("%H:%M") if run.completed_at else None,
        "books_open": run.books_open,
        "run_status": run.status,
    }


@router.get("/{rec_id}")
async def get_rec_case(rec_id: str, business_date: date = COB) -> dict:
    """The full case for one rec: header, analysis, groups, grounding.

    A rec with no breaks returns a case with `state: "clear"` rather than a
    404 or another rec's data — "nothing to review" is a real answer.
    """
    async with get_session() as s:
        await ensure_fixtures(s)
        rec, run = await _rec_and_run(s, rec_id, business_date)
        breaks = breaks_for_rec(rec_id)
        header = _header(rec, run)

        if not breaks:
            return {
                "state": "clear",
                "header": header,
                "pipeline_stages": PIPELINE_STAGES,
                "pipeline_stage": "notify" if run.status == "cleared" else "mbr",
                "draft": None,
                "pattern_groups": [],
                "deltas": {},
                "break_books": {},
                "reasons": {},
                "group_meta": {},
                "grounding": [],
                "evidence_gaps": [],
                "validation_errors": [],
                "model_skipped": None,
            }

        sid = session_id_for(rec_id)
        async with checkpointer() as cp:
            snapshot = await build_graph(cp, session=s).aget_state(
                {"configurable": {"thread_id": sid}}
            )
            if not snapshot.values:
                await run_investigation(
                    _initial_state(rec, run, breaks),
                    thread_id=sid,
                    session=s,
                    checkpointer=cp,
                )
                snapshot = await build_graph(cp, session=s).aget_state(
                    {"configurable": {"thread_id": sid}}
                )

        v = snapshot.values
        parked = snapshot.next == ("review",)
        draft = v.get("draft")
        return {
            "state": "open",
            "header": header | {
                "status": "awaiting_signoff" if parked else (v.get("outcome") or "analysing"),
            },
            "session_id": sid,
            "draft": draft.model_dump() if draft else None,
            "pattern_groups": [g.model_dump() for g in v.get("pattern_groups", [])],
            "deltas": v.get("deltas", {}),
            "break_books": {b["break_id"]: b["book_ref"] for b in v.get("breaks", [])},
            "reasons": v.get("reasons", {}),
            "group_meta": v.get("group_meta", {}),
            "grounding": await calls_for(s, sid),
            "pipeline_stage": "signoff" if parked else "analysis",
            "pipeline_stages": PIPELINE_STAGES,
            "evidence_gaps": v.get("evidence_gaps", []),
            "validation_errors": v.get("validation_errors", []),
            "model_skipped": v.get("model_skipped"),
        }
