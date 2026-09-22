"""Run schedule and header rollups, derived from rows.

Phase 1 served all of this from a static Python dict in api/routes/runs.py.
Every figure here is a query, so the screen cannot drift from the data.
"""

from datetime import date

from sqlalchemy import case, func, select

from app.db.models_graph import BreakEvent
from app.db.models_ops import Reconciliation, Run
from app.db.models_graph import Node

REGION_ORDER = ["APAC", "EMEA", "AMER"]

# What a controller is told the run windows are. Derived from the recs
# themselves rather than declared, so adding a rec at a new time shows up.
STATUS_CLEARED = "cleared"
STATUS_AWAITING = "awaiting"
STATUS_BLOCKED = "blocked"



def _hhmm(value) -> str:
    return value.strftime("%H:%M")


async def run_windows(session, business_date: date) -> list[str]:
    rows = await session.scalars(
        select(Run.scheduled_time)
        .where(Run.business_date == business_date)
        .distinct()
        .order_by(Run.scheduled_time)
    )
    return [_hhmm(t) for t in rows.all()]


async def regions_with_recs(session, business_date: date) -> list[dict]:
    """One row per rec that has a run on this date, grouped by region."""
    stmt = (
        select(
            Reconciliation.rec_id,
            Reconciliation.name,
            Reconciliation.region,
            Reconciliation.books_total,
            Run.scheduled_time,
            Run.status,
            Run.books_open,
            Run.completed_at,
            Run.run_id,
        )
        .join(Run, Run.rec_id == Reconciliation.rec_id)
        .where(Run.business_date == business_date)
        .order_by(Reconciliation.region, Run.scheduled_time, Reconciliation.rec_id)
    )
    rows = (await session.execute(stmt)).all()

    pending = await _adjustments_pending(session, business_date)

    by_region: dict[str, list[dict]] = {}
    for r in rows:
        by_region.setdefault(r.region, []).append(
            {
                "rec_id": r.rec_id,
                "run_id": r.run_id,
                "name": r.name,
                "scheduled": _hhmm(r.scheduled_time),
                "completed": _hhmm(r.completed_at) if r.completed_at else None,
                "status": r.status,
                "books_open": r.books_open,
                "books_total": r.books_total,
                "adj_pending": pending.get(r.rec_id, 0),
            }
        )

    ordered = [
        {"region": region, "recs": by_region[region]}
        for region in REGION_ORDER
        if region in by_region
    ]
    # Any region not in the declared order still appears, after the known ones.
    ordered += [
        {"region": region, "recs": recs}
        for region, recs in sorted(by_region.items())
        if region not in REGION_ORDER
    ]
    return ordered


async def _adjustments_pending(session, business_date: date) -> dict[str, int]:
    """Unresolved breaks per rec, on this date.

    Joined through the book's natural key rather than through
    investigation_session: the count has to be right before anyone opens a
    case, and a session row does not exist until an investigation runs.
    """
    stmt = (
        select(Reconciliation.rec_id, func.count(BreakEvent.break_id))
        .select_from(BreakEvent)
        .join(Node, Node.node_id == BreakEvent.book_id)
        .join(
            Reconciliation,
            Node.natural_key.like(Reconciliation.master_book + "-%"),
        )
        .where(
            BreakEvent.cob_date == business_date,
            BreakEvent.outcome.is_(None),
        )
        .group_by(Reconciliation.rec_id)
    )
    return {rec_id: count for rec_id, count in (await session.execute(stmt)).all()}


async def _clock(session, business_date: date) -> dict:
    """The "now 17:40 IST · next 19:00" line.

    For a historical business date there is no meaningful wall clock, so
    "now" is the last recorded activity on that date. "next" is the earliest
    window still scheduled after it. Both are read from rows rather than
    declared, so they cannot contradict the schedule beside them.
    """
    last_activity = await session.scalar(
        select(func.max(Run.completed_at)).where(Run.business_date == business_date)
    )
    now = _hhmm(last_activity) if last_activity else None

    stmt = (
        select(func.min(Run.scheduled_time))
        .where(Run.business_date == business_date, Run.status == "scheduled")
    )
    if last_activity is not None:
        stmt = stmt.where(Run.scheduled_time > last_activity.time())
    next_time = await session.scalar(stmt)

    if next_time is None:
        # Nothing later today still scheduled: fall back to the earliest
        # scheduled window, whenever it is.
        next_time = await session.scalar(
            select(func.min(Run.scheduled_time)).where(
                Run.business_date == business_date, Run.status == "scheduled"
            )
        )

    return {"now": now, "next_run": _hhmm(next_time) if next_time else None}


async def header_stats(session, business_date: date) -> dict:
    """The chip row: recs, cleared, awaiting, blocked, adj pending,
    auto-posted, books open, not open, unlocked."""
    status_counts = dict(
        (await session.execute(
            select(Run.status, func.count())
            .where(Run.business_date == business_date)
            .group_by(Run.status)
        )).all()
    )

    books = (
        await session.execute(
            select(
                func.coalesce(func.sum(Run.books_open), 0),
                func.coalesce(func.sum(Reconciliation.books_total), 0),
            )
            .select_from(Run)
            .join(Reconciliation, Reconciliation.rec_id == Run.rec_id)
            .where(Run.business_date == business_date)
        )
    ).one()
    books_open, books_total = int(books[0]), int(books[1])

    auto_posted = int(
        await session.scalar(
            select(func.count())
            .select_from(BreakEvent)
            .where(
                BreakEvent.cob_date == business_date,
                BreakEvent.outcome == "approved",
                BreakEvent.pattern_code == "P-204",
            )
        )
        or 0
    )

    pending = sum((await _adjustments_pending(session, business_date)).values())

    # A book is unlocked once every break on it is resolved.
    fully_resolved = (
        select(BreakEvent.book_id)
        .where(BreakEvent.cob_date == business_date)
        .group_by(BreakEvent.book_id)
        .having(func.sum(case((BreakEvent.outcome.is_(None), 1), else_=0)) == 0)
        .subquery()
    )
    unlocked = int(
        await session.scalar(select(func.count()).select_from(fully_resolved)) or 0
    )

    unlocked_total = int(
        await session.scalar(
            select(func.count(func.distinct(BreakEvent.book_id))).where(
                BreakEvent.cob_date == business_date
            )
        )
        or 0
    )

    clock = await _clock(session, business_date)

    return {
        "recs": sum(status_counts.values()),
        "cleared": status_counts.get(STATUS_CLEARED, 0),
        "awaiting": status_counts.get(STATUS_AWAITING, 0),
        "blocked": status_counts.get(STATUS_BLOCKED, 0),
        "adj_pending": pending,
        "auto_posted": auto_posted,
        "books_open": books_open,
        "books_not_open": books_total - books_open,
        "unlocked": unlocked,
        "unlocked_total": unlocked_total,
        "business_date": str(business_date),
        "timezone": "IST",
        "now": clock["now"],
        "next_run": clock["next_run"],
    }
