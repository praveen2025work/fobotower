"""Run a rec's investigation, and read how it executed.

  POST /api/recs/{rec_id}/investigate   run it once; idempotent on a repeat
  GET  /api/recs/{rec_id}/trace         each LangGraph step, from the checkpoints

Starting a run is deliberately its own verb, separate from the console's own
`GET /api/recs/{rec_id}` (fobo/web/routes/console.py): a read should not have to run
an investigation as a side effect for a caller that only wants to trigger one
(the e2e test, scripts/run_investigation.py, and the older classic console
all used a GET for this).
"""

from datetime import date

from fastapi import APIRouter, HTTPException

from fobo.web.investigations import open_investigation, rec_and_run, session_id_for
from fobo.web.dependencies import checkpointer, ensure_seed_data
from fobo.db.base import get_session
from fobo.reports.trace import execution_trace
from seed_data.history import COB, breaks_for_rec

router = APIRouter(prefix="/api/recs", tags=["investigations"])


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


@router.post("/{rec_id}/investigate")
async def investigate(rec_id: str, business_date: date = COB) -> dict:
    """Run the investigation if it has not run yet; a repeat call reads the
    same checkpoint rather than running it again."""
    async with get_session() as s:
        await ensure_seed_data(s)
        rec, run = await rec_and_run(s, rec_id, business_date)
        if not breaks_for_rec(rec_id):
            raise HTTPException(status_code=409, detail=f"nothing to investigate for {rec_id}")
        await open_investigation(s, rec, run)
        sid = session_id_for(rec_id)
        async with checkpointer() as cp:
            trace = await execution_trace(cp, s, sid)
        return {
            "session_id": sid,
            "status": trace["status"],
            "workflow_version": trace["workflow_version"],
        }


@router.get("/{rec_id}/trace")
async def get_rec_trace(rec_id: str, business_date: date = COB) -> dict:
    """How this rec's investigation executed: each LangGraph step, in order,
    with its timing and what it produced — read from the checkpoints."""
    async with get_session() as s:
        await ensure_seed_data(s)
        rec, run = await rec_and_run(s, rec_id, business_date)
        header = _header(rec, run)
        if not breaks_for_rec(rec_id):
            return {"header": header, "state": "clear", "trace": None}
        async with checkpointer() as cp:
            trace = await execution_trace(cp, s, session_id_for(rec_id))
        return {"header": header, "state": "open", "trace": trace}
