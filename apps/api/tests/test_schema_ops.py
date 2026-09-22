from datetime import date, time

from sqlalchemy import select

from app.db.base import get_session
from app.db.models_graph import BreakEvent
from app.db.models_ops import Reconciliation, Run, SourceCall


async def test_reconciliation_carries_region_and_schedule():
    cols = Reconciliation.__table__.columns
    for name in ("rec_id", "name", "region", "scheduled_time", "books_total"):
        assert name in cols, f"reconciliation is missing {name}"


async def test_run_records_scheduled_and_completed_times():
    """The rec header shows 'R-1055 · 11:00 · 11:52 IST': the scheduled
    time and the actual completion time are different facts."""
    cols = Run.__table__.columns
    assert "scheduled_time" in cols
    assert "completed_at" in cols
    assert cols["completed_at"].nullable is True


async def test_source_call_records_what_the_grounding_panel_shows():
    cols = SourceCall.__table__.columns
    for name in (
        "call_id",
        "investigation_session_id",
        "application_name",
        "tool_name",
        "validated_parameters",
        "row_count",
        "result_summary",
        "entitlement_result",
        "latency_ms",
        "called_ts",
    ):
        assert name in cols, f"source_call is missing {name}"


async def test_break_event_carries_a_business_reason():
    cols = BreakEvent.__table__.columns
    assert "reason_text" in cols
    assert "is_ungrounded" in cols
    assert "first_seen_run_id" in cols


async def test_can_round_trip_a_run():
    async with get_session() as s:
        s.add(
            Reconciliation(
                rec_id="R-1055",
                name="Rec Factory — Cash Recon",
                region="APAC",
                scheduled_time=time(11, 0),
                books_total=11,
                master_book="APAC-CASH",
            )
        )
        await s.flush()
        s.add(
            Run(
                run_id="run-1055-20260803",
                rec_id="R-1055",
                business_date=date(2026, 8, 3),
                scheduled_time=time(11, 0),
                completed_at=None,
                status="awaiting",
                books_open=9,
            )
        )
        await s.commit()
        got = await s.scalar(select(Run).where(Run.run_id == "run-1055-20260803"))
        assert got.status == "awaiting"
        assert got.books_open == 9
