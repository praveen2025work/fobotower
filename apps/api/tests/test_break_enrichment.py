from datetime import date

from sqlalchemy import select

from app.contracts.models import Caller
from app.db.base import get_session
from app.db.models_graph import BreakEvent
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.resolve import resolve
from app.workflow.session import ensure_investigation_session
from fixtures.loader import load_all, read_breaks

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}


def breaks_with_causes():
    return [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in read_breaks()]


async def _run(session, breaks=None, run_id="run-1100"):
    st = {
        "investigation_session_id": f"sess-enrich-{run_id}",
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": run_id,
        "caller": FO,
        "breaks": breaks if breaks is not None else breaks_with_causes(),
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }
    await ensure_investigation_session(session, st)
    st |= await resolve(st, session=session)
    st |= await gather(st, session=session)
    st |= await group(st, session=session)
    return st


async def test_each_break_gets_the_mock_reason_wording():
    async with get_session() as s:
        await load_all(s)
        st = await _run(s)
        assert st["reasons"]["B-1"] == "Nostro statement received after 23:30 cutoff"
        assert st["reasons"]["B-7"] == "Reference does not resolve in static data"
        assert st["reasons"]["B-12"] == "Pending desk confirmation since the 11:00 run"
        assert st["reasons"]["B-10"] == "Two entries with identical settlement reference"


async def test_every_break_has_a_reason():
    """A blank reason renders as an empty cell nobody notices."""
    async with get_session() as s:
        await load_all(s)
        st = await _run(s)
        assert len(st["reasons"]) == 14
        assert all(st["reasons"].values())


async def test_reasons_are_persisted_so_later_runs_can_read_them():
    async with get_session() as s:
        await load_all(s)
        await _run(s)
        row = await s.scalar(select(BreakEvent).where(BreakEvent.break_id == "B-1"))
        assert row.reason_text == "Nostro statement received after 23:30 cutoff"
        assert row.first_seen_run_id == "run-1100"


async def test_a_group_reports_how_many_of_its_breaks_are_ungrounded():
    """The mock badges CPTY-REF with '1 ungrounded'."""
    async with get_session() as s:
        await load_all(s)
        # Mark one CPTY-REF break as ungrounded, as the validator would.
        row = await s.scalar(select(BreakEvent).where(BreakEvent.break_id == "B-7"))
        row.is_ungrounded = True
        await s.commit()

        st = await _run(s)
        cpty = next(g for g in st["pattern_groups"] if g.pattern_code == "CPTY-REF")
        assert st["group_meta"][cpty.group_id]["ungrounded_count"] == 1

        p204 = next(g for g in st["pattern_groups"] if g.pattern_code == "P-204")
        assert st["group_meta"][p204.group_id]["ungrounded_count"] == 0


async def test_carried_runs_counts_distinct_runs_a_break_appeared_in():
    """The mock badges LATE-BOOK 'carried 3 runs'. first_seen_run_id is set
    once; a later run finding the same break does not overwrite it."""
    async with get_session() as s:
        await load_all(s)
        await _run(s, run_id="run-1100")
        row = await s.scalar(select(BreakEvent).where(BreakEvent.break_id == "B-12"))
        assert row.first_seen_run_id == "run-1100"

        await _run(s, run_id="run-1500")
        row = await s.scalar(select(BreakEvent).where(BreakEvent.break_id == "B-12"))
        assert row.first_seen_run_id == "run-1100", "first_seen was overwritten"


async def test_a_group_with_no_carried_breaks_reports_zero():
    async with get_session() as s:
        await load_all(s)
        st = await _run(s)
        for g in st["pattern_groups"]:
            assert st["group_meta"][g.group_id]["carried_runs"] == 0
