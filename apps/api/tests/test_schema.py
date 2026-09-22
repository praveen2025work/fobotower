from datetime import date

from sqlalchemy import select

from app.db.base import get_session
from app.db.models_graph import BreakEvent, Node
from app.db.models_session import InvestigationSession


async def test_node_requires_legal_entity_id():
    """legal_entity_id is a first-class column, not a JSONB path,
    because the entitlement predicate filters on it in every query."""
    cols = Node.__table__.columns
    assert "legal_entity_id" in cols
    assert cols["legal_entity_id"].nullable is False


async def test_node_is_bitemporal():
    cols = Node.__table__.columns
    for name in ("valid_from", "valid_to", "recorded_from", "recorded_to"):
        assert name in cols, f"node is missing {name}"


async def test_break_event_is_not_bitemporal():
    """A break is an event that happened, not a fact whose validity changes."""
    assert "valid_from" not in BreakEvent.__table__.columns


async def test_can_insert_and_read_a_session():
    async with get_session() as s:
        s.add(
            InvestigationSession(
                investigation_session_id="sess-1",
                reconciliation_id="R-1055",
                master_book="APAC-CASH",
                business_date=date(2026, 8, 3),
                run_id="run-1100",
                status="analysing",
            )
        )
        await s.commit()
        got = await s.scalar(
            select(InvestigationSession).where(
                InvestigationSession.investigation_session_id == "sess-1"
            )
        )
        assert got.reconciliation_id == "R-1055"
