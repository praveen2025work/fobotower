"""Seven days of run history, and today as the Helix console shows it.

Figures like a 7-day pattern history, a median draft-to-sign-off time and a
"carried N sessions" badge cannot come from a single run. This seeds the rows
they derive from, so nothing on screen is a literal.

Today (the business date) is deliberately incomplete: Prime is awaiting
sign-off, Collateral is blocked, FI Credit is mid-analysis, and two recs are
still waiting for their Ready event. The scenario itself is in catalogue.py.
"""

import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select, update

from app.db.models_graph import BreakEvent, Node
from app.db.models_ops import Reconciliation, Run
from app.db.models_session import ControllerDecision, InvestigationSession
from fixtures.catalogue import (
    ENTITY,
    OPEN_REC_BREAKS,
    P204_HISTORY_DAYS,
    PATTERN_MIX,
    PRIME_CARRIED,
    PRIME_UNGROUNDED,
    REC_BY_ID,
    RECS,
    RESOLVED_TODAY,
    TODAY,
    master_book_ref,
)

COB = date(2026, 8, 3)
HISTORY_DAYS = 7

# approved/total per day for R-1055's P-204 resolutions, keyed by date.
P204_HISTORY = {
    COB - timedelta(days=HISTORY_DAYS - 1 - i): counts
    for i, counts in enumerate(P204_HISTORY_DAYS)
}

# Rows history.py owns, by break id prefix, so a reseed clears exactly them.
_OWNED_BREAK_PREFIXES = ("hist-", "A-", "C-", "F-", "COLL-")


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=timezone.utc)


def _run_id(rec_id: str, day: date) -> str:
    return f"run-{rec_id}-{day:%Y%m%d}"


async def load_history(session, *, commit: bool = True) -> None:
    """Idempotent: clears its own rows first, then reseeds."""
    await _clear(session)
    await _load_recs(session)
    await session.flush()
    await _load_runs(session)
    await session.flush()
    await _load_history_books(session)
    await session.flush()
    await _load_resolved_breaks(session)
    await session.flush()
    await _load_open_rec_breaks(session)
    await _load_resolved_today(session)
    await _mark_prime_breaks(session)
    if commit:
        await session.commit()


async def _clear(session) -> None:
    await session.execute(delete(ControllerDecision))
    for prefix in _OWNED_BREAK_PREFIXES:
        await session.execute(
            delete(BreakEvent).where(BreakEvent.break_id.like(f"{prefix}%"))
        )
    await session.execute(
        delete(InvestigationSession).where(
            InvestigationSession.investigation_session_id.like("hist-%")
        )
    )
    await session.execute(delete(Run))
    await session.execute(delete(Reconciliation))
    await session.execute(delete(Node).where(Node.node_id.like("book:HIST-%")))
    for rec in RECS:
        if rec.rec_id == "R-1055":
            continue  # loader.py owns the Prime books
        await session.execute(
            delete(Node).where(Node.node_id.like(f"book:{rec.master_book}-%"))
        )


async def _load_recs(session) -> None:
    for rec in RECS:
        session.add(
            Reconciliation(
                rec_id=rec.rec_id,
                name=rec.name,
                region=rec.region,
                master_book=rec.master_book,
                scheduled_time=rec.scheduled,
                books_total=rec.books_total,
                rec_group=rec.group,
                l4=rec.l4,
                ccy=rec.ccy,
            )
        )


def _event_id(rec_id: str, day: date) -> str:
    """Past runs' Ready events: stable, and distinct from today's."""
    return f"EVT-RDY-{int(rec_id[2:]) * 10 + day.day % 10:05d}"


async def _load_runs(session) -> None:
    rng = random.Random(1055)
    for offset in range(HISTORY_DAYS - 1, 0, -1):
        day = COB - timedelta(days=offset)
        for rec in RECS:
            # Past runs all cleared, a few minutes after their window.
            ready = _at(day, rec.scheduled) + timedelta(minutes=rng.randint(2, 20))
            completed = ready + timedelta(minutes=rng.randint(12, 40))
            session.add(
                Run(
                    run_id=_run_id(rec.rec_id, day),
                    rec_id=rec.rec_id,
                    business_date=day,
                    scheduled_time=rec.scheduled,
                    completed_at=completed,
                    status="cleared",
                    books_open=rec.books_total,
                    ready_event_id=_event_id(rec.rec_id, day),
                    ready_at=ready,
                    mb_available=rec.books_total,
                    mb_reported_at=ready - timedelta(minutes=2),
                    book_stats={
                        "total": rec.books_total, "autoPost": rec.books_total,
                        "cleared": 0, "awaiting": 0, "analysing": 0,
                        "blocked": 0, "notOpen": 0,
                    },
                    books_unlocked=rec.books_total,
                )
            )

    for rec in RECS:
        today = TODAY[rec.rec_id]
        session.add(
            Run(
                run_id=_run_id(rec.rec_id, COB),
                rec_id=rec.rec_id,
                business_date=COB,
                scheduled_time=rec.scheduled,
                completed_at=_at(COB, today.completed) if today.completed else None,
                status=today.status,
                books_open=rec.books_total - today.book_stats["notOpen"],
                ready_event_id=today.ready_event_id,
                ready_at=_at(COB, today.ready_at) if today.ready_at else None,
                mb_available=today.mb_available,
                mb_reported_at=_at(COB, today.mb_reported_at),
                book_stats=today.book_stats,
                books_unlocked=today.books_unlocked,
            )
        )


async def _load_history_books(session) -> None:
    """Books the historical breaks hang off. Distinct from today's Prime
    books so history and today's population never collide."""
    for i in range(1, 13):
        session.add(
            Node(
                node_id=f"book:HIST-{i:02d}",
                node_type="Book",
                natural_key=f"HIST-{i:02d}",
                legal_entity_id=ENTITY,
                valid_from=date(2020, 1, 1),
            )
        )


async def _load_resolved_breaks(session) -> None:
    """Resolved breaks per day, with decisions carrying real timestamps.

    P-204 counts match the 7-day history exactly. The other patterns get a
    smaller spread so the analytics split is not uniform.
    """
    rng = random.Random(204)
    seq = 0
    prime = REC_BY_ID["R-1055"]

    for day, (approved, total) in P204_HISTORY.items():
        run_id = _run_id("R-1055", day)
        outcomes = ["approved"] * approved + ["rejected"] * (total - approved)
        sid = f"hist-R-1055-{day:%Y%m%d}"
        # created_ts is set explicitly rather than defaulting to now():
        # sign-off duration is decided_ts minus this, and a historical
        # session measured against today's clock reads as negative.
        opened_at = _at(day, prime.scheduled) + timedelta(minutes=35)
        session.add(
            InvestigationSession(
                investigation_session_id=sid,
                reconciliation_id="R-1055",
                master_book=prime.master_book,
                business_date=day,
                run_id=run_id,
                status="recorded",
                created_ts=opened_at,
            )
        )
        await session.flush()

        drafted_at = _at(day, prime.scheduled) + timedelta(minutes=40)
        for outcome in outcomes:
            seq += 1
            session.add(
                BreakEvent(
                    break_id=f"hist-{seq:04d}",
                    book_id=f"book:HIST-{(seq % 12) + 1:02d}",
                    line_code="CASH",
                    cob_date=day,
                    fo_value=100000.0,
                    bo_value=99000.0,
                    delta=1000.0,
                    pattern_code="P-204",
                    outcome=outcome,
                    narrative="FX timing lag",
                    reason_text="Nostro statement received after 23:30 cutoff",
                    first_seen_run_id=run_id,
                )
            )
            # Median sign-off lands around 18 minutes.
            session.add(
                ControllerDecision(
                    decision_id=f"hist-dec-{seq:04d}",
                    investigation_session_id=sid,
                    group_id=None,
                    controller_user_id="praveen",
                    action="approve" if outcome == "approved" else "reject",
                    reason=None if outcome == "approved" else "Amount unverified",
                    idempotency_key=f"hist-idem-{seq:04d}",
                    decided_ts=drafted_at + timedelta(minutes=rng.randint(11, 26)),
                )
            )

        # A thinner spread of the other three patterns per day.
        for code in PATTERN_MIX[1:]:
            for _ in range(rng.randint(1, 3)):
                seq += 1
                session.add(
                    BreakEvent(
                        break_id=f"hist-{seq:04d}",
                        book_id=f"book:HIST-{(seq % 12) + 1:02d}",
                        line_code="CASH",
                        cob_date=day,
                        fo_value=100000.0,
                        bo_value=98500.0,
                        delta=1500.0,
                        pattern_code=code,
                        outcome="approved" if rng.random() < 0.8 else "rejected",
                        narrative=code,
                        first_seen_run_id=run_id,
                    )
                )


async def _add_book(session, ref: str) -> None:
    if await session.get(Node, f"book:{ref}") is None:
        session.add(
            Node(
                node_id=f"book:{ref}",
                node_type="Book",
                natural_key=ref,
                legal_entity_id=ENTITY,
                valid_from=date(2020, 1, 1),
            )
        )
        await session.flush()


async def _load_open_rec_breaks(session) -> None:
    """Books and breaks for the recs whose investigation runs today."""
    for rec_id, rows in OPEN_REC_BREAKS.items():
        rec = REC_BY_ID[rec_id]
        for b in rows:
            ref = master_book_ref(rec, b.book_no)
            await _add_book(session, ref)
            session.add(
                BreakEvent(
                    break_id=b.break_id,
                    book_id=f"book:{ref}",
                    line_code="CASH",
                    cob_date=COB,
                    fo_value=100000.0 + b.delta,
                    bo_value=100000.0,
                    delta=b.delta,
                    outcome=None,
                    first_seen_run_id=_run_id(
                        rec_id, COB - timedelta(days=b.first_seen_days_ago)
                    ),
                )
            )


async def _load_resolved_today(session) -> None:
    """Cleared recs: what their sessions resolved earlier today."""
    for rec_id, rows in RESOLVED_TODAY.items():
        rec = REC_BY_ID[rec_id]
        for b in rows:
            ref = master_book_ref(rec, b.book_no)
            await _add_book(session, ref)
            session.add(
                BreakEvent(
                    break_id=b.break_id,
                    book_id=f"book:{ref}",
                    line_code="CASH",
                    cob_date=COB,
                    fo_value=100000.0 + b.delta,
                    bo_value=100000.0,
                    delta=b.delta,
                    pattern_code=b.pattern_code,
                    outcome=b.outcome,
                    narrative=b.label,
                    reason_text=b.reason,
                    first_seen_run_id=_run_id(rec_id, COB),
                )
            )


async def _mark_prime_breaks(session) -> None:
    """Carry and grounding flags on the Prime population loader.py seeds."""
    for break_id, days_ago in PRIME_CARRIED.items():
        await session.execute(
            update(BreakEvent)
            .where(BreakEvent.break_id == break_id)
            .values(first_seen_run_id=_run_id("R-1055", COB - timedelta(days=days_ago)))
        )
    await session.execute(
        update(BreakEvent)
        .where(BreakEvent.break_id.in_(PRIME_UNGROUNDED))
        .values(is_ungrounded=True)
    )


def breaks_for_rec(rec_id: str) -> list[dict]:
    """The break population an investigation of this rec should analyse."""
    if rec_id == "R-1055":
        # The Prime population, defined in data/breaks_small.json.
        from fixtures.loader import read_breaks

        return read_breaks()

    rec = REC_BY_ID.get(rec_id)
    if rec is None or rec_id not in OPEN_REC_BREAKS:
        return []
    return [
        {
            "break_id": b.break_id,
            "book_ref": master_book_ref(rec, b.book_no),
            "line_code": "CASH",
            "fo_value": 100000.0 + b.delta,
            "bo_value": 100000.0,
            "cause": b.cause,
        }
        for b in OPEN_REC_BREAKS[rec_id]
    ]


async def history_is_loaded(session) -> bool:
    return bool(await session.scalar(select(Reconciliation.rec_id).limit(1)))
