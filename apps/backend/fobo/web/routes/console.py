"""The console's API.

  GET  /api/board                   every rec, its session, the feed
  GET  /api/recs/{rec_id}           one rec, after something changed
  POST /api/recs/{rec_id}/messages  ask the session a question
  POST /api/recs/{rec_id}/decisions approve or reject adjustments

Views are composed in fobo.console_views; this layer opens investigations (it owns
the checkpointer) and turns requests into database writes. Starting a run
from scratch is a separate verb — see fobo.web/routes/investigations.py.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from fobo.web.auth import current_caller, dev_callers
from fobo.web.investigations import open_investigation, rec_and_run, session_id_for
from fobo.web.decisions import DecisionRequest, apply_decision
from fobo.web.dependencies import ensure_seed_data
from fobo.db.base import get_session
from fobo.db.models_ops import Reconciliation, Run
from fobo.console_views import activity
from fobo.console_views.board import live_view, rec_header, recorded_view, running_view
from fobo.console_views.calls import SessionTools
from fobo.console_views.chat import answer
from fobo.console_views.fmt import money0
from fobo.console_views.session import (
    add_message,
    conversation,
    ensure_session_row,
    message_view,
    open_recorded_session,
    workspace,
)
from fobo.reports.hours_saved import hours_saved
from fobo.investigation import versions
from seed_data.history import COB

router = APIRouter(prefix="/api", tags=["helix"])

# How a caller's role reads in the header, most senior first.
ROLE_TITLES = [("PC", "FOBO Controller"), ("FO", "Front Office")]


def _caller() -> dict:
    c = current_caller()
    title = next((t for role, t in ROLE_TITLES if role in c.roles), ", ".join(c.roles))
    return {"id": c.staff_id, "name": c.staff_id.capitalize(), "title": title}


async def _view(s, rec, run) -> dict:
    sid = session_id_for(rec.rec_id)
    if run.status in ("awaiting", "blocked"):
        snapshot = await open_investigation(s, rec, run)
        view = (
            await live_view(s, rec, run, snapshot.values, sid)
            if snapshot else rec_header(rec, run)
        )
    elif run.status == "cleared":
        view = await recorded_view(s, rec, run, sid)
        await open_recorded_session(s, rec, run, sid, view)
    elif run.status == "in_progress":
        view = running_view(rec, run)
    else:
        view = rec_header(rec, run)
    view["session"], view["calls"] = await conversation(s, view)
    return view


async def _today(s, business_date: date) -> list:
    return (await s.execute(
        select(Reconciliation, Run)
        .join(Run, Run.rec_id == Reconciliation.rec_id)
        .where(Run.business_date == business_date)
        .order_by(Reconciliation.scheduled_time, Reconciliation.rec_id)
    )).all()


async def _feed(s, business_date: date, rows, views: dict[str, dict]) -> list[dict]:
    events = [e for rec, run in rows for e in activity.run_events(rec, run, views[rec.rec_id])]
    events += await activity.decision_events(s, business_date, views)
    return activity.feed(events)


@router.get("/board")
async def board(business_date: date = COB) -> dict:
    async with get_session() as s:
        await ensure_seed_data(s)
        rows = await _today(s, business_date)
        views = {rec.rec_id: await _view(s, rec, run) for rec, run in rows}
        body = {
            "cob": str(business_date),
            "caller": _caller(),
            "recs": [views[rec.rec_id] for rec, _ in rows],
            "activity": await _feed(s, business_date, rows, views),
            # Derived with its assumption stated, e.g. "36 decisions avoided at
            # 12 min each"; the console shows the value and the basis together.
            "hoursSaved": await hours_saved(s, business_date),
        }
        callers = dev_callers()
        if callers:
            body["devCallers"] = callers
        return body


@router.get("/recs/{rec_id}")
async def rec(rec_id: str, business_date: date = COB) -> dict:
    async with get_session() as s:
        await ensure_seed_data(s)
        r, run = await rec_and_run(s, rec_id, business_date)
        return await _view(s, r, run)


class Question(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/recs/{rec_id}/messages", status_code=201)
async def ask(rec_id: str, body: Question, business_date: date = COB) -> dict:
    question = body.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="the question is empty")
    async with get_session() as s:
        await ensure_seed_data(s)
        r, run = await rec_and_run(s, rec_id, business_date)
        view = await _view(s, r, run)
        sid = view["sessionId"]
        if sid is None:
            # No session until the Ready event arrives and analysis finishes.
            raise HTTPException(status_code=409, detail=f"{rec_id} has no open session yet")
        await ensure_session_row(s, r, run, sid, "analysing")

        active = await versions.active(s)
        tools = SessionTools(s, sid, workspace(view, business_date))
        intent, blocks = await answer(
            view, question, tools, cob=str(business_date),
            analysis_call_ids=[c["id"] for c in view["calls"]],
            reasoner=active.config.settings.reason.reasoner,
        )
        await s.flush()
        asked = await add_message(s, sid, "user", text=question)
        replied = await add_message(s, sid, "agent", blocks=blocks, call_ids=tools.call_ids,
                                    answered_by=f"router:{intent}")
        await s.commit()
        return {
            "user": await message_view(s, asked, view["ccy"]),
            "agent": await message_view(s, replied, view["ccy"]),
        }


class HelixDecision(BaseModel):
    ids: list[str] = Field(min_length=1)
    decision: Literal["Approved", "Rejected"]
    reason: str | None = None


@router.post("/recs/{rec_id}/decisions", status_code=201)
async def decide(rec_id: str, body: HelixDecision,
                 idempotency_key: str = Header(alias="Idempotency-Key"),
                 business_date: date = COB) -> dict:
    """Approve or reject the selected adjustments, once both confirmations
    are ticked in the console. Returns the rec as it now stands."""
    action = "approve" if body.decision == "Approved" else "reject"
    async with get_session() as s:
        await ensure_seed_data(s)
        r, run = await rec_and_run(s, rec_id, business_date)
        before = await _view(s, r, run)
        pending = {a["id"] for a in before["adjustments"] if a["status"] == "Pending"}
        stale = [i for i in body.ids if i not in pending]
        if stale:
            raise HTTPException(status_code=409,
                                detail=f"no longer pending: {', '.join(stale)}")
        await apply_decision(
            s, rec_id,
            DecisionRequest(action=action, reason=body.reason, break_ids=body.ids),
            idempotency_key,
        )
        amounts = {a["id"]: a["delta"] for a in before["adjustments"]}
        total = money0(sum(amounts[i] for i in body.ids), r.ccy)
        verb = "approved" if action == "approve" else "rejected"
        who = _caller()["name"]
        n = len(body.ids)
        text = (f"{who} {verb} {n} adjustment{'s' if n > 1 else ''} "
                f"({', '.join(body.ids)}), {total}"
                + (". Released to FAS for MOTIF posting." if action == "approve"
                   else f". Reason: {body.reason}"))
        await add_message(s, before["sessionId"], "system", text=text, tone=verb)
        await s.commit()
        rows = await _today(s, business_date)
        views = {x.rec_id: (await _view(s, x, xr)) for x, xr in rows}
        return {"rec": views[rec_id], "activity": await _feed(s, business_date, rows, views)}
