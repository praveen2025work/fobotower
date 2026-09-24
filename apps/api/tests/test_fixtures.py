from datetime import date

from sqlalchemy import func, select

from app.db.base import get_session
from app.db.models_graph import BreakEvent, Edge, Node
from fixtures.loader import load_all


async def test_loads_fourteen_breaks():
    async with get_session() as s:
        await load_all(s)
        n = await s.scalar(
            select(func.count())
            .select_from(BreakEvent)
            .where(BreakEvent.outcome.is_(None))
        )
        assert n == 14


async def test_a_book_hierarchy_changes_mid_period():
    """Proves as_of correctness is testable: one book moved desk on 2026-07-01."""
    async with get_session() as s:
        await load_all(s)
        rows = (
            await s.scalars(
                select(Edge).where(
                    Edge.from_node_id == "book:PRIME-MB-05",
                    Edge.edge_type == "BELONGS_TO",
                )
            )
        ).all()
        assert len(rows) == 2, "expected a closed edge and an open one"
        closed = [r for r in rows if r.valid_to is not None]
        assert len(closed) == 1
        assert closed[0].valid_to == date(2026, 6, 30)


async def test_prior_resolutions_yield_the_mock_approval_rate():
    async with get_session() as s:
        await load_all(s)
        priors = (
            await s.scalars(
                select(BreakEvent).where(
                    BreakEvent.pattern_code == "P-204",
                    BreakEvent.outcome.isnot(None),
                )
            )
        ).all()
        assert len(priors) == 42
        approved = [p for p in priors if p.outcome == "approved"]
        assert round(len(approved) / len(priors), 2) == 0.88


async def test_every_node_has_a_legal_entity():
    async with get_session() as s:
        await load_all(s)
        n = await s.scalar(
            select(func.count()).select_from(Node).where(Node.legal_entity_id.is_(None))
        )
        assert n == 0
