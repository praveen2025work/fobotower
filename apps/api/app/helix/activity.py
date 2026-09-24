"""The notification feed, as the Helix bell shows it.

Derived, never stored: each run contributes the events its state implies,
timed from its own timestamps, and each controller decision today adds one.
An event log that could disagree with the runs it describes would be worse
than none.
"""

from datetime import date

from sqlalchemy import select

from app.db.models_session import ControllerDecision, InvestigationSession
from app.helix.fmt import hhmm, money0
from app.helix.session import ist_hhmm


def _short(name: str) -> str:
    """'Rec Factory — Cash' reads as 'Rec Factory Cash' after a colon."""
    return name.replace(" — ", " ")


def run_events(rec, run, view: dict) -> list[dict]:
    rid, l4 = rec.rec_id, rec.l4
    events = []
    if run.ready_at is None:
        events.append({"at": run.mb_reported_at, "time": hhmm(run.mb_reported_at), "recId": rid, "type": "event",
                       "text": f"MB Rec readiness (One Fin UX): {l4} "
                               f"{run.mb_available}/{rec.books_total} master books ready"})
        return events
    events.append({"at": run.ready_at, "time": hhmm(run.ready_at), "recId": rid, "type": "event",
                   "text": f"Ready event {run.ready_event_id} received: {l4} session started"})
    done, at = hhmm(run.completed_at), run.completed_at
    if run.status == "awaiting" and done:
        adjs = view["adjustments"]
        patterns = len({a["pattern"] for a in adjs})
        events.append({"at": at, "time": done, "recId": rid, "type": "awaiting",
                       "text": f"Awaiting sign-off: {l4}, {len(adjs)} adjustments across "
                               f"{patterns} patterns"})
    elif run.status == "blocked" and done:
        events.append({"at": at, "time": done, "recId": rid, "type": "blocked",
                       "text": f"Blocked: {l4} source-system correction required"})
    elif run.status == "cleared" and done:
        events.append({"at": at, "time": done, "recId": rid, "type": "cleared",
                       "text": f"Rec Cleared: {_short(rec.name)}"})
        events.append({"at": at, "time": done, "recId": rid, "type": "unlocked",
                       "text": f"Book Unlocked: {run.books_unlocked} books via "
                               "Master Book ↔ P&L Mapping"})
    return events


async def decision_events(s, business_date: date, views: dict[str, dict]) -> list[dict]:
    rows = (await s.execute(
        select(ControllerDecision, InvestigationSession.reconciliation_id)
        .join(InvestigationSession,
              InvestigationSession.investigation_session_id
              == ControllerDecision.investigation_session_id)
        .where(InvestigationSession.business_date == business_date,
               ControllerDecision.break_ids.is_not(None))
    )).all()
    events = []
    for d, rec_id in rows:
        view = views.get(rec_id)
        if view is None:
            continue
        amounts = {a["id"]: a["delta"] for a in view["adjustments"]}
        total = sum(amounts.get(b, 0.0) for b in d.break_ids)
        verb = "Approved" if d.action == "approve" else "Rejected"
        events.append({"at": d.decided_ts, "time": ist_hhmm(d.decided_ts), "recId": rec_id,
                       "type": verb.lower(),
                       "text": f"{verb}: {len(d.break_ids)} adj on {view['l4']} "
                               f"({money0(total, view['ccy'])})"})
    return events


# At one timestamp, a cleared run's unlock reads above its clear.
_ORDER = {"unlocked": 0, "cleared": 1}


def feed(events: list[dict]) -> list[dict]:
    """Newest first, by the full timestamp: a decision made now sorts above
    the business day's events even when its clock time reads earlier."""
    ordered = sorted(
        (e for e in events if e["at"]),
        key=lambda e: (e["at"], -_ORDER.get(e["type"], 2)),
        reverse=True,
    )
    return [{k: v for k, v in e.items() if k != "at"} for e in ordered]
