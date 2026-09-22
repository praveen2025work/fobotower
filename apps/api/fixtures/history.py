"""Seven days of run history.

The mock shows figures that cannot come from a single run: a 7-day pattern
history, a median draft-to-sign-off time, and a "carried N runs" badge. This
seeds the rows those derive from, so nothing on screen is a literal.

Today (the business date) is deliberately left incomplete: R-1055 is awaiting
sign-off, R-2015 is blocked, and two recs have not opened. That is the state
the mock renders.
"""

import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select

from app.db.models_graph import BreakEvent, Node
from app.db.models_ops import Reconciliation, Run
from app.db.models_session import ControllerDecision, InvestigationSession

COB = date(2026, 8, 3)
HISTORY_DAYS = 7
ENTITY = "LE-APAC-01"

# The mock's seven recs. books_total and the run-window times come straight
# from its timeline and region rail.
RECS = [
    ("R-1050", "CATS vs MOTIF — Rates", "APAC", "APAC-RATES", time(11, 0), 22),
    ("R-1055", "Rec Factory — Cash Recon", "APAC", "APAC-CASH", time(11, 0), 11),
    ("R-1060", "CATS vs MOTIF — FX", "APAC", "APAC-FX", time(19, 0), 15),
    ("R-2010", "CATS vs MOTIF — Credit", "EMEA", "EMEA-CREDIT", time(15, 0), 19),
    ("R-2015", "Rec Factory — Collateral", "EMEA", "EMEA-COLL", time(15, 0), 7),
    ("R-3010", "CATS vs MOTIF — Equities", "AMER", "AMER-EQ", time(17, 0), 41),
    ("R-3015", "Rec Factory — Cash Recon", "AMER", "AMER-CASH", time(17, 0), 13),
]

# Today's state, as the mock shows it: rec_id -> (status, books_open).
TODAY_STATE = {
    "R-1050": ("cleared", 22),
    "R-1055": ("awaiting", 9),
    "R-1060": ("scheduled", 0),
    "R-2010": ("in_progress", 11),
    "R-2015": ("blocked", 1),
    "R-3010": ("scheduled", 0),
    "R-3015": ("cleared", 13),
}

# Completion times for today's finished runs, so the rec header can show
# "R-1055 · 11:00 · 11:52 IST".
TODAY_COMPLETED = {
    "R-1050": time(11, 38),
    "R-1055": time(11, 52),
    "R-2010": time(15, 41),
    "R-3015": time(17, 29),
}

PATTERN_MIX = ["P-204", "CPTY-REF", "LATE-BOOK", "DUP-SETTLE"]

# The mock's 7-day pattern history for P-204: approved/total per day.
# 03 Aug is today's run, resolved earlier in the day.
P204_HISTORY = {
    date(2026, 7, 28): (4, 5),
    date(2026, 7, 29): (3, 4),
    date(2026, 7, 30): (2, 3),
    date(2026, 7, 31): (2, 2),
    date(2026, 8, 1): (8, 9),
    date(2026, 8, 2): (8, 8),
    date(2026, 8, 3): (7, 7),
}


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
    if commit:
        await session.commit()


async def _clear(session) -> None:
    await session.execute(delete(ControllerDecision))
    await session.execute(
        delete(BreakEvent).where(BreakEvent.break_id.like("hist-%"))
    )
    await session.execute(
        delete(InvestigationSession).where(
            InvestigationSession.investigation_session_id.like("hist-%")
        )
    )
    await session.execute(delete(Run))
    await session.execute(delete(Reconciliation))
    await session.execute(delete(Node).where(Node.node_id.like("book:HIST-%")))
    for prefix in ("EMEA-CREDIT", "EMEA-COLL"):
        await session.execute(
            delete(BreakEvent).where(BreakEvent.book_id.like(f"book:{prefix}-%"))
        )
        await session.execute(
            delete(Node).where(Node.node_id.like(f"book:{prefix}-%"))
        )


async def _load_recs(session) -> None:
    for rec_id, name, region, book, sched, total in RECS:
        session.add(
            Reconciliation(
                rec_id=rec_id,
                name=name,
                region=region,
                master_book=book,
                scheduled_time=sched,
                books_total=total,
            )
        )


def _run_id(rec_id: str, day: date) -> str:
    return f"run-{rec_id}-{day:%Y%m%d}"


async def _load_runs(session) -> None:
    rng = random.Random(1055)
    for offset in range(HISTORY_DAYS - 1, 0, -1):
        day = COB - timedelta(days=offset)
        for rec_id, _n, _r, _b, sched, total in RECS:
            # Past runs all completed, a few minutes after their window.
            completed = datetime.combine(
                day, sched, tzinfo=timezone.utc
            ) + timedelta(minutes=rng.randint(22, 58))
            session.add(
                Run(
                    run_id=_run_id(rec_id, day),
                    rec_id=rec_id,
                    business_date=day,
                    scheduled_time=sched,
                    completed_at=completed,
                    status="cleared",
                    books_open=total,
                )
            )

    for rec_id, _n, _r, _b, sched, _t in RECS:
        status, books_open = TODAY_STATE[rec_id]
        done = TODAY_COMPLETED.get(rec_id)
        session.add(
            Run(
                run_id=_run_id(rec_id, COB),
                rec_id=rec_id,
                business_date=COB,
                scheduled_time=sched,
                completed_at=(
                    datetime.combine(COB, done, tzinfo=timezone.utc) if done else None
                ),
                status=status,
                books_open=books_open,
            )
        )


async def _load_history_books(session) -> None:
    """Books the historical breaks hang off. Distinct from today's APAC-CASH
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

    P-204 counts match the mock's 7-day history exactly. The other patterns
    get a smaller spread so the analytics split is not uniform.
    """
    rng = random.Random(204)
    seq = 0

    for day, (approved, total) in P204_HISTORY.items():
        run_id = _run_id("R-1055", day)
        sched = time(11, 0)
        outcomes = ["approved"] * approved + ["rejected"] * (total - approved)
        sid = f"hist-R-1055-{day:%Y%m%d}"
        # created_ts is set explicitly rather than defaulting to now():
        # sign-off duration is decided_ts minus this, and a historical
        # session measured against today's clock reads as negative.
        opened_at = datetime.combine(day, sched, tzinfo=timezone.utc) + timedelta(
            minutes=35
        )
        session.add(
            InvestigationSession(
                investigation_session_id=sid,
                reconciliation_id="R-1055",
                master_book="APAC-CASH",
                business_date=day,
                run_id=run_id,
                status="recorded",
                created_ts=opened_at,
            )
        )
        await session.flush()

        drafted_at = datetime.combine(day, sched, tzinfo=timezone.utc) + timedelta(
            minutes=40
        )
        for i, outcome in enumerate(outcomes):
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
            # Median sign-off lands around 18 minutes, as the mock reports.
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


# Recs with work waiting get their own break population, so switching recs
# shows that rec's data rather than an empty panel. Cleared and scheduled
# recs deliberately get none: that is what "cleared" means.
OPEN_REC_BREAKS = {
    "R-2010": [
        ("C1", 4210.0), ("C1", 1890.0), ("C1", 2650.0),
        ("C3", 11400.0), ("C3", 7320.0),
        ("C4", 980.0), ("C4", 3115.0), ("C4", 1745.0),
    ],
    "R-2015": [
        ("C2", 22400.0), ("C2", 8650.0),
        ("C6", 5120.0), ("C6", 3380.0), ("C6", 1290.0),
    ],
}


async def _load_open_rec_breaks(session) -> None:
    """Books and breaks for the recs that are mid-flight."""
    by_id = {r[0]: r for r in RECS}
    for rec_id, rows in OPEN_REC_BREAKS.items():
        _id, _name, _region, master_book, _sched, _total = by_id[rec_id]
        run_id = _run_id(rec_id, COB)
        for i, (cause, delta) in enumerate(rows, start=1):
            book = f"{master_book}-{i:02d}"
            session.add(
                Node(
                    node_id=f"book:{book}",
                    node_type="Book",
                    natural_key=book,
                    legal_entity_id=ENTITY,
                    valid_from=date(2020, 1, 1),
                )
            )
        await session.flush()
        for i, (cause, delta) in enumerate(rows, start=1):
            book = f"{master_book}-{i:02d}"
            session.add(
                BreakEvent(
                    break_id=f"{rec_id.lower()}-b{i:02d}",
                    book_id=f"book:{book}",
                    line_code="CASH",
                    cob_date=COB,
                    fo_value=100000.0 + delta,
                    bo_value=100000.0,
                    delta=delta,
                    outcome=None,
                    first_seen_run_id=run_id,
                )
            )


def breaks_for_rec(rec_id: str) -> list[dict]:
    """The break population an investigation of this rec should analyse."""
    if rec_id == "R-1055":
        # The mock's own population, defined in loader.py.
        from fixtures.loader import read_breaks

        return read_breaks()

    by_id = {r[0]: r for r in RECS}
    if rec_id not in OPEN_REC_BREAKS:
        return []
    master_book = by_id[rec_id][3]
    return [
        {
            "break_id": f"{rec_id.lower()}-b{i:02d}",
            "book_ref": f"{master_book}-{i:02d}",
            "line_code": "CASH",
            "fo_value": 100000.0 + delta,
            "bo_value": 100000.0,
            "cause": cause,
        }
        for i, (cause, delta) in enumerate(OPEN_REC_BREAKS[rec_id], start=1)
    ]


async def history_is_loaded(session) -> bool:
    return bool(await session.scalar(select(Reconciliation.rec_id).limit(1)))
