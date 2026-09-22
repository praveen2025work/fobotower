"""Notification activity feed.

Derived from run state rather than stored as messages: an event log that can
disagree with the runs it describes is worse than no log. Each run
contributes the events its status implies, timestamped from its own
completion.
"""

from datetime import date

from sqlalchemy import select

from app.db.models_ops import Reconciliation, Run

# Books unlocked per cleared run is the run's own book count; the mock's
# "19 books" and "34 books" are just two runs' totals.
KIND_TONE = {
    "notified": "green",
    "unlocked": "blue",
    "cleared": "green",
    "blocked": "red",
    "analysing": "blue",
    "awaiting": "amber",
}


def _hhmm(value) -> str:
    return value.strftime("%H:%M")


async def activity_feed(session, business_date: date, limit: int = 20) -> list[dict]:
    rows = (
        await session.execute(
            select(Reconciliation, Run)
            .join(Run, Run.rec_id == Reconciliation.rec_id)
            .where(Run.business_date == business_date)
            .order_by(Run.completed_at.desc().nullslast(), Run.scheduled_time.desc())
        )
    ).all()

    events: list[dict] = []
    for rec, run in rows:
        at = _hhmm(run.completed_at) if run.completed_at else _hhmm(run.scheduled_time)

        if run.status == "cleared":
            events.append(_event(at, "notified",
                                 f"P&L Agent notified — {rec.region} {_short(rec.name)} books"))
            events.append(_event(at, "unlocked",
                                 f"Book Unlocked — {rec.books_total} books via "
                                 "Master Book ↔ P&L Mapping"))
            events.append(_event(at, "cleared", f"Rec Cleared — {_short(rec.name)}"))
        elif run.status == "blocked":
            events.append(_event(at, "blocked",
                                 "Blocked — source-system correction required"))
        elif run.status == "in_progress":
            events.append(_event(at, "analysing", f"Analysis started — {rec.name}"))
        elif run.status == "awaiting":
            events.append(_event(at, "awaiting",
                                 "Awaiting sign-off — adjustments drafted, "
                                 "pending controller review"))

    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def _short(name: str) -> str:
    """'Rec Factory — Cash Recon' reads as 'Rec Factory Cash Recon' in the
    feed, where the em dash would collide with the event's own dash."""
    return name.replace("—", "").replace("  ", " ").strip()


def _event(at: str, kind: str, text: str) -> dict:
    return {"at": at, "kind": kind, "tone": KIND_TONE[kind], "text": text}
