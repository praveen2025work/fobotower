"""Open, run and read an investigation session."""

from datetime import date

from fastapi import APIRouter, HTTPException, Response

from api.auth import current_caller
from api.cases import CAUSE_TO_SNAPSHOT
from api.deps import checkpointer, ensure_fixtures
from app.db.base import get_session
from app.workflow.graph import graph_for_session, run_investigation
from fixtures.loader import read_breaks

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


PIPELINE_STAGES = [
    {"key": "mbr", "label": "MBR / Rec Factory", "sub": "CATS ↔ MOTIF breaks"},
    {
        "key": "analysis",
        "label": "FOBO Agent Analysis",
        "sub": "Manual / Auto adjustments",
    },
    {"key": "signoff", "label": "Human Sign-off", "sub": "Reviewed & approved"},
    {"key": "post", "label": "Post to MOTIF", "sub": "via FAS"},
    {"key": "notify", "label": "Notify P&L Agent", "sub": "Book Unlocked"},
]


def _initial_state(session_id: str) -> dict:
    return {
        "investigation_session_id": session_id,
        "reconciliation_id": "R-1055",
        "master_book": "PRIME-MB",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": current_caller(),
        "breaks": [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in read_breaks()],
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }


async def load_snapshot(session_id: str):
    async with get_session() as s:
        async with checkpointer() as cp:
            graph, _ = await graph_for_session(cp, s, session_id)
            return await graph.aget_state({"configurable": {"thread_id": session_id}})


@router.post("/{session_id}/investigate", status_code=202)
async def investigate(session_id: str) -> Response:
    async with get_session() as s:
        await ensure_fixtures(s)
        async with checkpointer() as cp:
            await run_investigation(
                _initial_state(session_id),
                thread_id=session_id,
                session=s,
                checkpointer=cp,
            )
    return Response(status_code=202)


@router.get("/{session_id}")
async def get_session_detail(session_id: str) -> dict:
    snapshot = await load_snapshot(session_id)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="no such investigation session")

    v = snapshot.values
    parked_at_review = snapshot.next == ("review",)
    draft = v.get("draft")

    return {
        "session": {
            "investigation_session_id": session_id,
            "reconciliation_id": v["reconciliation_id"],
            "master_book": v["master_book"],
            "business_date": str(v["business_date"]),
            "run_id": v["run_id"],
            "region": v["caller"].region,
            "status": "awaiting_signoff"
            if parked_at_review
            else (v.get("outcome") or "analysing"),
        },
        "draft": draft.model_dump() if draft else None,
        "pattern_groups": [g.model_dump() for g in v.get("pattern_groups", [])],
        "deltas": v.get("deltas", {}),
        # break_id -> book_ref, so adjustment rows can show the book the
        # controller recognises rather than an internal break id.
        "break_books": {b["break_id"]: b["book_ref"] for b in v.get("breaks", [])},
        "pipeline_stage": "signoff" if parked_at_review else "analysis",
        "pipeline_stages": PIPELINE_STAGES,
        "evidence_gaps": v.get("evidence_gaps", []),
        "validation_errors": v.get("validation_errors", []),
        "model_skipped": v.get("model_skipped"),
    }
