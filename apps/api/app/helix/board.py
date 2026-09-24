"""One rec, as the Helix console renders it.

The run's status decides where each part comes from:

  scheduled    nothing yet: only master-book readiness
  in_progress  the analysis is running
  awaiting     the live investigation, parked at human sign-off
  blocked      the live investigation, with nothing it could draft
  cleared      the breaks it resolved earlier today

The investigation itself is supplied by the caller (the API layer owns the
checkpointer), so this module stays a pure read over the database.
"""

from datetime import date

from sqlalchemy import select

from app.db.models_graph import BreakEvent, Node
from app.db.models_ops import Run
from app.graph.ontology import OntologyRepository
from app.helix import analysis
from app.helix.adjustments import live_adjustments, recorded_adjustments
from app.helix.fmt import hhmm
from app.helix.rec_state import helix_status, steps


def rec_header(rec, run) -> dict:
    stamp = run.completed_at or run.ready_at
    return {
        "id": rec.rec_id,
        "name": rec.name,
        "group": rec.rec_group,
        "l4": rec.l4,
        "ccy": rec.ccy,
        "readyAt": hhmm(run.ready_at),
        "eventId": run.ready_event_id,
        "mb": {"available": run.mb_available, "total": rec.books_total},
        "bookStats": run.book_stats,
        "status": helix_status(run.status),
        "steps": steps(run.status),
        "booksUnlocked": run.books_unlocked,
        "updated": f"{hhmm(stamp)} IST" if stamp else "—",
        "sessionId": None,
        # True when a LangGraph investigation ran for this rec, so there is a
        # step-by-step execution trace to show.
        "graphRun": False,
        "analysis": None,
        "adjustments": [],
    }


async def aged_sessions(s, rec_id: str, first_seen: dict[str, str | None],
                        cob: date) -> dict[str, int]:
    """Per break, how many of this rec's earlier runs it was already open in."""
    runs = (await s.execute(
        select(Run.run_id, Run.business_date).where(Run.rec_id == rec_id)
    )).all()
    day_of = {run_id: day for run_id, day in runs}
    earlier = sorted(day for day in day_of.values() if day < cob)
    out = {}
    for bid, run_id in first_seen.items():
        since = day_of.get(run_id)
        out[bid] = 0 if since is None else sum(1 for d in earlier if d >= since)
    return out


async def _escalation_routes(s, findings: dict, as_of: date) -> dict[str, str]:
    repo = OntologyRepository(s)
    codes = {f.get("category_code") for f in findings.values() if f.get("category_code")}
    routes = {}
    for code in codes:
        route = await repo.escalation_route(code, as_of)
        if route:
            routes[code] = route
    return routes


async def _break_rows(s, break_ids: list[str]) -> dict[str, BreakEvent]:
    if not break_ids:
        return {}
    rows = (await s.scalars(
        select(BreakEvent).where(BreakEvent.break_id.in_(break_ids))
    )).all()
    return {r.break_id: r for r in rows}


async def live_view(s, rec, run, values: dict, session_id: str) -> dict:
    """Awaiting sign-off or blocked: built from the checkpointed investigation."""
    cob = run.business_date
    breaks = values.get("breaks", [])
    rows = await _break_rows(s, [b["break_id"] for b in breaks])
    aged = await aged_sessions(
        s, rec.rec_id, {bid: r.first_seen_run_id for bid, r in rows.items()}, cob
    )
    findings = values.get("findings", {})
    routes = await _escalation_routes(s, findings, cob)
    adjs = live_adjustments(values, rows, aged, routes, rec.ccy, cob)

    view = rec_header(rec, run) | {
        "sessionId": session_id, "adjustments": adjs, "graphRun": True,
    }
    if run.status == "blocked":
        escalated = [b for b in breaks if findings.get(b["break_id"], {}).get("verdict") == "ESCALATE"]
        view["analysis"] = analysis.blocked(
            rec, escalated or breaks, findings, aged, values.get("reasons", {}), routes
        )
        first = (escalated or breaks)[0]
        view["blockedBreak"] = {
            "id": first["break_id"],
            "book": first["book_ref"],
            "amount": first["fo_value"] - first["bo_value"],
        }
        view["breakNote"] = view["analysis"]["why"]
    else:
        view["analysis"] = analysis.live(values, adjs)
    return view


async def recorded_view(s, rec, run, session_id: str) -> dict:
    """Cleared earlier today: the breaks that run resolved."""
    cob = run.business_date
    rows = (await s.execute(
        select(BreakEvent, Node.natural_key)
        .join(Node, Node.node_id == BreakEvent.book_id)
        .where(
            Node.natural_key.like(f"{rec.master_book}-%"),
            BreakEvent.cob_date == cob,
            BreakEvent.outcome.is_not(None),
        )
    )).all()
    # A-2 before A-10: break ids sort by their number, not as text.
    rows = sorted(rows, key=lambda r: (r[0].break_id.rsplit("-", 1)[0],
                                       int(r[0].break_id.rsplit("-", 1)[-1] or 0)))
    aged = await aged_sessions(
        s, rec.rec_id, {r.break_id: r.first_seen_run_id for r, _ in rows}, cob
    )
    adjs = recorded_adjustments(rows, aged, rec.ccy, cob)
    view = rec_header(rec, run) | {"sessionId": session_id, "adjustments": adjs}
    view["analysis"] = analysis.recorded(rec, run, adjs) if adjs else None
    return view


def running_view(rec, run) -> dict:
    return rec_header(rec, run) | {"analysis": analysis.running(rec)}
