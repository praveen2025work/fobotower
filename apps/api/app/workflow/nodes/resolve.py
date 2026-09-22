"""Resolve each break's book, pinned to as_of = business_date.

Zero matches escalates UNRESOLVED_BOOK. Multiple matches escalates
AMBIGUOUS_BOOK and never auto-picks: picking one of two candidate books
silently attributes a P&L adjustment to the wrong desk.
"""

from app.graph.errors import AmbiguousBook, UnresolvedBook
from app.graph.repository import GraphRepository
from app.workflow.state import InvestigationState


async def resolve(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    as_of = state["business_date"]
    caller = state["caller"]
    resolutions: dict[str, str] = {}

    for brk in state["breaks"]:
        try:
            resolutions[brk["break_id"]] = await repo.resolve_book(
                brk["book_ref"], as_of, caller
            )
        except UnresolvedBook:
            return {
                "outcome": "escalated",
                "escalation_reason": "UNRESOLVED_BOOK",
                "as_of": as_of,
                "book_resolutions": resolutions,
            }
        except AmbiguousBook:
            return {
                "outcome": "escalated",
                "escalation_reason": "AMBIGUOUS_BOOK",
                "as_of": as_of,
                "book_resolutions": resolutions,
            }

    return {"book_resolutions": resolutions, "as_of": as_of}
