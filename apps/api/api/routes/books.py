"""Book detail: what a controller sees when they click a book name.

Answers the question the adjustment row raises but cannot fit: what else is
wrong with this book, where does it sit, and has it done this before.
"""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.auth import current_caller
from api.deps import ensure_fixtures
from app.db.base import get_session
from app.db.models_graph import BreakEvent, Node
from app.graph.errors import UnresolvedBook
from app.graph.repository import GraphRepository
from fixtures.history import COB

router = APIRouter(prefix="/api/books", tags=["books"])

HISTORY_LOOKBACK_DAYS = 180


@router.get("/{book_ref}")
async def get_book(book_ref: str, business_date: date = COB) -> dict:
    caller = current_caller()
    async with get_session() as s:
        await ensure_fixtures(s)
        repo = GraphRepository(s)

        try:
            book_id = await repo.resolve_book(book_ref, business_date, caller)
        except UnresolvedBook:
            # Entitlement is enforced in the query, so "not visible to you"
            # and "does not exist" are deliberately the same answer here.
            raise HTTPException(status_code=404, detail=f"no such book: {book_ref}")

        context = await repo.book_context(book_id, business_date, caller)

        today = (
            await s.scalars(
                select(BreakEvent)
                .where(
                    BreakEvent.book_id == book_id,
                    BreakEvent.cob_date == business_date,
                )
                .order_by(BreakEvent.break_id)
            )
        ).all()

        priors = await repo.similar_breaks(
            book_id, "CASH", business_date, HISTORY_LOOKBACK_DAYS, caller
        )

        node = await s.scalar(select(Node).where(Node.node_id == book_id))

        open_count = sum(1 for b in today if b.outcome is None)
        return {
            "book_ref": book_ref,
            "book_id": book_id,
            "desk": context["desk"],
            "legal_entity_id": node.legal_entity_id if node else None,
            "business_date": str(business_date),
            "open_breaks": open_count,
            "total_breaks": len(today),
            "breaks": [
                {
                    "break_id": b.break_id,
                    "line_code": b.line_code,
                    "fo_value": float(b.fo_value) if b.fo_value is not None else None,
                    "bo_value": float(b.bo_value) if b.bo_value is not None else None,
                    "delta": float(b.delta) if b.delta is not None else None,
                    "pattern_code": b.pattern_code,
                    "reason_text": b.reason_text,
                    "outcome": b.outcome,
                    "is_ungrounded": b.is_ungrounded,
                    "first_seen_run_id": b.first_seen_run_id,
                }
                for b in today
            ],
            "history": [
                {
                    "break_id": p["break_id"],
                    "cob_date": str(p["cob_date"]),
                    "pattern_code": p["pattern_code"],
                    "outcome": p["outcome"],
                    "narrative": p["narrative"],
                }
                for p in priors
            ],
        }
