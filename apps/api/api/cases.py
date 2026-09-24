"""Open a rec's investigation: read it from the checkpoint, or run it once.

The legacy rec route and the Helix board both need a rec's case. A rec with
work to analyse runs its graph the first time anyone asks, and every later
read comes from the checkpoint.
"""

import asyncio
from collections import defaultdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select

from api.auth import current_caller
from api.deps import checkpointer
from app.db.models_ops import Reconciliation, Run
from app.workflow.graph import build_graph, run_investigation
from fixtures.history import breaks_for_rec

# Maps each fixture break's declared cause to the snapshot fields that make
# the corresponding check fire. Phase 3 replaces this with the CATS and
# MOTIF adapters.
CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C3": {"bo_dataset_id": "EOD-2026-08-02"},
    "C4": {"fo_components": ["principal", "fee"]},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}

# One investigation per rec at a time. The console fetches twice on mount in
# development, and two concurrent first reads would both run the graph and
# record every call twice. A single API process serves this, so an in-process
# lock is enough.
_opening: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def session_id_for(rec_id: str) -> str:
    return f"sess-{rec_id.lower()}"


async def rec_and_run(s, rec_id: str, business_date: date):
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


def initial_state(rec, run, breaks: list[dict]) -> dict:
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


async def open_case(s, rec, run):
    """The rec's checkpointed state, running the investigation if it has not
    run yet. None when the rec has nothing to analyse."""
    breaks = breaks_for_rec(rec.rec_id)
    if not breaks:
        return None
    sid = session_id_for(rec.rec_id)
    config = {"configurable": {"thread_id": sid}}
    async with _opening[rec.rec_id]:
        async with checkpointer() as cp:
            snapshot = await build_graph(cp, session=s).aget_state(config)
            if not snapshot.values:
                await run_investigation(
                    initial_state(rec, run, breaks),
                    thread_id=sid,
                    session=s,
                    checkpointer=cp,
                )
                # Nodes after group record calls without committing; the
                # checkpoint is durable, so their rows must be too, or a later
                # read finds a finished investigation missing its last calls.
                await s.commit()
                snapshot = await build_graph(cp, session=s).aget_state(config)
    return snapshot


async def read_case(s, rec_id: str):
    """The checkpointed state only; never runs anything."""
    async with checkpointer() as cp:
        snapshot = await build_graph(cp, session=s).aget_state(
            {"configurable": {"thread_id": session_id_for(rec_id)}}
        )
    return snapshot if snapshot.values else None
