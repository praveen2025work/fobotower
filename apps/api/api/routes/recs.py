"""Rec-scoped investigation.

The console navigates by rec, not by opaque session id: selecting a rec in
the rail must load that rec's case. A session id is derived from the rec so
the two stay in step.
"""

from datetime import date

from fastapi import APIRouter

from api.cases import open_case, rec_and_run, session_id_for
from api.deps import checkpointer, ensure_fixtures
from api.routes.sessions import PIPELINE_STAGES
from app.db.base import get_session
from app.grounding.recorder import calls_for
from app.queries.trace import execution_trace
from fixtures.history import COB, breaks_for_rec

router = APIRouter(prefix="/api/recs", tags=["recs"])




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
        rec, run = await rec_and_run(s, rec_id, business_date)
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
                "findings": {},
                "determinism": None,
            }

        sid = session_id_for(rec_id)
        snapshot = await open_case(s, rec, run)

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
            # Per break: pattern or rule applied, category, guarded verdict,
            # and why a guard overrode it. The deterministic share of the run
            # is the orchestrator's headline figure.
            "findings": v.get("findings", {}),
            "determinism": v.get("determinism"),
            "reasoning_error": v.get("reasoning_error"),
        }


@router.get("/{rec_id}/trace")
async def get_rec_trace(rec_id: str, business_date: date = COB) -> dict:
    """How this rec's investigation executed: each LangGraph step, in order,
    with its timing and what it produced — read from the checkpoints."""
    async with get_session() as s:
        await ensure_fixtures(s)
        rec, run = await rec_and_run(s, rec_id, business_date)
        header = _header(rec, run)
        if not breaks_for_rec(rec_id):
            return {"header": header, "state": "clear", "trace": None}
        async with checkpointer() as cp:
            trace = await execution_trace(cp, s, session_id_for(rec_id))
        return {"header": header, "state": "open", "trace": trace}
