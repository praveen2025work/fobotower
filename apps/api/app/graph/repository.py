"""Graph repository. Every method takes as_of and caller.

Neither is optional and neither has a default — a method that could be
called without them would eventually be called without them.
"""

from datetime import date, timedelta

from sqlalchemy import and_, or_, select

from app.contracts.models import Caller
from app.db.models_graph import BreakEvent, Edge, Node
from app.graph.entitlement import build_entitlement_predicate
from app.graph.errors import AmbiguousBook, UnresolvedBook
from app.graph.queries.postgres import LINEAGE_CTE

MAX_LINEAGE_DEPTH = 4
MAX_SIMILAR_BREAKS = 20


def _valid_at(model, as_of: date):
    """Bitemporal validity window. Pins a read to the state in force on as_of."""
    return and_(
        model.valid_from <= as_of,
        or_(model.valid_to.is_(None), model.valid_to >= as_of),
    )


class GraphRepository:
    def __init__(self, session):
        self._s = session

    async def resolve_book(self, book_ref: str, as_of: date, caller: Caller) -> str:
        rows = (
            await self._s.scalars(
                select(Node).where(
                    Node.node_type == "Book",
                    Node.natural_key == book_ref,
                    _valid_at(Node, as_of),
                    build_entitlement_predicate(caller),
                )
            )
        ).all()
        if not rows:
            raise UnresolvedBook(book_ref)
        if len(rows) > 1:
            raise AmbiguousBook(f"{book_ref} resolved to {len(rows)} nodes")
        return rows[0].node_id

    async def book_context(self, book_id: str, as_of: date, caller: Caller) -> dict:
        desk_id = await self._s.scalar(
            select(Edge.to_node_id).where(
                Edge.from_node_id == book_id,
                Edge.edge_type == "BELONGS_TO",
                _valid_at(Edge, as_of),
            )
        )
        desk = None
        if desk_id is not None:
            desk = await self._s.scalar(
                select(Node).where(
                    Node.node_id == desk_id,
                    _valid_at(Node, as_of),
                    build_entitlement_predicate(caller),
                )
            )
        return {
            "book_id": book_id,
            "desk": desk.natural_key if desk else None,
            "legal_entity_id": desk.legal_entity_id if desk else None,
            "as_of": as_of,
        }

    async def lineage(
        self, book_id: str, direction: str, depth: int, as_of: date, caller: Caller
    ) -> list[dict]:
        result = await self._s.execute(
            LINEAGE_CTE,
            {
                "book_id": book_id,
                "edge_type": direction,
                "as_of": as_of,
                "max_depth": min(depth, MAX_LINEAGE_DEPTH),
            },
        )
        candidates = {r.node_id: r.depth for r in result}
        if not candidates:
            return []
        visible = (
            await self._s.scalars(
                select(Node).where(
                    Node.node_id.in_(candidates),
                    _valid_at(Node, as_of),
                    build_entitlement_predicate(caller),
                )
            )
        ).all()
        return [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "natural_key": n.natural_key,
                "depth": candidates[n.node_id],
            }
            for n in visible
        ]

    async def similar_breaks(
        self,
        book_id: str,
        line_code: str,
        cob_date: date,
        lookback: int,
        caller: Caller,
        limit: int = MAX_SIMILAR_BREAKS,
    ) -> list[dict]:
        """Structural query first: it bounds the candidate set.

        pgvector reranks within this set in Phase 3 — it never widens it
        beyond what this query and the entitlement predicate allow.
        """
        floor = cob_date - timedelta(days=lookback)
        rows = (
            await self._s.scalars(
                select(BreakEvent)
                .join(Node, Node.node_id == BreakEvent.book_id)
                .where(
                    BreakEvent.book_id == book_id,
                    BreakEvent.line_code == line_code,
                    BreakEvent.cob_date >= floor,
                    BreakEvent.cob_date < cob_date,
                    BreakEvent.outcome.isnot(None),
                    _valid_at(Node, cob_date),
                    build_entitlement_predicate(caller),
                )
                .order_by(BreakEvent.cob_date.desc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "break_id": r.break_id,
                "book_id": r.book_id,
                "pattern_code": r.pattern_code,
                "outcome": r.outcome,
                "narrative": r.narrative,
                "cob_date": r.cob_date,
            }
            for r in rows
        ]
