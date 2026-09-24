"""Phase 1's proof.

If an investigation cannot checkpoint at the human interrupt and resume to
completion from a fresh process, nothing else in the architecture matters:
a controller who steps away loses the run.
"""

from datetime import date

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.contracts.models import Caller
from app.db.base import DATABASE_URL, get_session
from app.workflow.graph import build_graph, resume_investigation, run_investigation
from fixtures.loader import load_all, read_breaks

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
DSN = DATABASE_URL.replace("+asyncpg", "")

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}


def _initial_state(session_id: str) -> dict:
    return {
        "investigation_session_id": session_id,
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": FO,
        "breaks": [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in read_breaks()],
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }


@pytest.fixture
async def checkpointer():
    async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
        await cp.setup()
        yield cp


async def test_run_pauses_at_the_review_interrupt(checkpointer):
    async with get_session() as s:
        await load_all(s)
        state = await run_investigation(
            _initial_state("sess-pause"),
            thread_id="sess-pause",
            session=s,
            checkpointer=checkpointer,
        )
    assert state["draft"] is not None
    assert len(state["pattern_groups"]) == 4
    assert state.get("outcome") is None, "must not have completed"


async def test_state_survives_a_fresh_process_and_resumes_to_completion():
    """A second, independent checkpointer connection picks the thread up
    exactly where it paused — as a restarted worker would."""
    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            await run_investigation(
                _initial_state("sess-resume"),
                thread_id="sess-resume",
                session=s,
                checkpointer=cp,
            )

    # Nothing from the first connection survives into this block.
    async with get_session() as s2:
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp2:
            snapshot = await build_graph(cp2, session=s2).aget_state(
                {"configurable": {"thread_id": "sess-resume"}}
            )
            assert snapshot.next == ("review",), "thread is not parked at review"
            assert len(snapshot.values["pattern_groups"]) == 4

            final = await resume_investigation(
                "sess-resume",
                decisions=[
                    {"group_id": g.group_id, "action": "approve"}
                    for g in snapshot.values["pattern_groups"]
                ],
                session=s2,
                checkpointer=cp2,
            )
            assert final["outcome"] == "recorded"


async def test_an_approved_run_writes_tomorrows_priors():
    """record stamps each break with its pattern and outcome so a later
    run's similar_breaks can find it."""
    from sqlalchemy import select

    from app.db.models_graph import BreakEvent

    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            await run_investigation(
                _initial_state("sess-priors"),
                thread_id="sess-priors",
                session=s,
                checkpointer=cp,
            )
            snapshot = await build_graph(cp, session=s).aget_state(
                {"configurable": {"thread_id": "sess-priors"}}
            )
            await resume_investigation(
                "sess-priors",
                decisions=[
                    {"group_id": g.group_id, "action": "approve"}
                    for g in snapshot.values["pattern_groups"]
                ],
                session=s,
                checkpointer=cp,
            )

    async with get_session() as s2:
        brk = await s2.scalar(select(BreakEvent).where(BreakEvent.break_id == "B-1"))
        assert brk.pattern_code == "P-204"
        assert brk.outcome == "approved"


async def test_an_unresolvable_book_escalates_without_reaching_review(checkpointer):
    async with get_session() as s:
        await load_all(s)
        st = _initial_state("sess-esc") | {
            "breaks": [
                {
                    "break_id": "b-x",
                    "book_ref": "NOPE-01",
                    "line_code": "CASH",
                    "fo_value": 1.0,
                    "bo_value": 0.0,
                }
            ],
        }
        state = await run_investigation(
            st, thread_id="sess-esc", session=s, checkpointer=checkpointer
        )
    assert state["outcome"] == "escalated"
    assert state["escalation_reason"] == "UNRESOLVED_BOOK"
