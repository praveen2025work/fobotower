from datetime import date

from sqlalchemy import func, select

from app.db.base import get_session
from app.db.models_graph import BreakEvent
from app.db.models_ops import Reconciliation, Run
from app.db.models_session import ControllerDecision
from fixtures.history import COB, HISTORY_DAYS, P204_HISTORY, load_history


async def test_seeds_the_mocks_seven_recs_across_three_regions():
    async with get_session() as s:
        await load_history(s)
        recs = (await s.scalars(select(Reconciliation))).all()
        assert len(recs) == 7
        assert {r.region for r in recs} == {"APAC", "EMEA", "AMER"}


async def test_seeds_one_run_per_rec_per_day():
    async with get_session() as s:
        await load_history(s)
        n = await s.scalar(select(func.count()).select_from(Run))
        assert n == 7 * HISTORY_DAYS


async def test_todays_runs_match_the_mocks_states():
    async with get_session() as s:
        await load_history(s)
        today = {
            r.rec_id: (r.status, r.books_open)
            for r in (
                await s.scalars(select(Run).where(Run.business_date == COB))
            ).all()
        }
        assert today["R-1055"] == ("awaiting", 9)
        assert today["R-2015"] == ("blocked", 1)
        assert today["R-1050"] == ("cleared", 22)


async def test_a_completed_run_records_when_it_finished():
    """The rec header shows 'R-1055 · 11:00 · 11:52 IST'."""
    async with get_session() as s:
        await load_history(s)
        run = await s.scalar(
            select(Run).where(Run.rec_id == "R-1055", Run.business_date == COB)
        )
        assert run.completed_at is not None
        assert run.completed_at.hour == 11
        assert run.completed_at.minute == 52


async def test_a_scheduled_run_has_not_completed():
    async with get_session() as s:
        await load_history(s)
        run = await s.scalar(
            select(Run).where(Run.rec_id == "R-1060", Run.business_date == COB)
        )
        assert run.completed_at is None


async def test_p204_history_reproduces_the_mocks_seven_day_chart():
    async with get_session() as s:
        await load_history(s)
        for day, (approved, total) in P204_HISTORY.items():
            rows = (
                await s.scalars(
                    select(BreakEvent).where(
                        BreakEvent.pattern_code == "P-204",
                        BreakEvent.cob_date == day,
                        BreakEvent.outcome.isnot(None),
                    )
                )
            ).all()
            assert len(rows) == total, f"{day}: expected {total} breaks"
            got = sum(1 for r in rows if r.outcome == "approved")
            assert got == approved, f"{day}: expected {approved} approved"


async def test_decisions_carry_timestamps_a_median_can_be_computed_from():
    async with get_session() as s:
        await load_history(s)
        n = await s.scalar(select(func.count()).select_from(ControllerDecision))
        assert n > 0
        row = await s.scalar(select(ControllerDecision))
        assert row.decided_ts is not None


async def test_load_history_is_idempotent():
    async with get_session() as s:
        await load_history(s)
        first = await s.scalar(select(func.count()).select_from(Run))
        await load_history(s)
        second = await s.scalar(select(func.count()).select_from(Run))
        assert first == second
