"""A Helix session: its row, its conversation, and the calls behind it.

The session opens with the analysis turn, whose MCP calls are the ones the
investigation made. Everything after that (questions, answers, decision
notes) is a stored message. An answer's calls are referenced by id, so the
analysis turn shows only what the investigation itself retrieved.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.models_ops import SourceCall
from app.db.models_session import InvestigationSession, SessionMessage
from app.helix.calls import SessionTools, calls_by_id, session_calls

IST = timezone(timedelta(hours=5, minutes=30))


def ist_hhmm(ts: datetime) -> str:
    return ts.astimezone(IST).strftime("%H:%M")


def workspace(rec_view: dict, cob) -> dict:
    return {"workspace": rec_view["group"], "l4": rec_view["l4"], "cob": str(cob)}


async def ensure_session_row(s, rec, run, session_id: str, status: str) -> None:
    """Idempotent, like the investigation's own: the primary key decides."""
    await s.execute(
        insert(InvestigationSession)
        .values(
            investigation_session_id=session_id,
            reconciliation_id=rec.rec_id,
            master_book=rec.master_book,
            business_date=run.business_date,
            run_id=run.run_id,
            status=status,
        )
        .on_conflict_do_nothing(index_elements=["investigation_session_id"])
    )


async def open_recorded_session(s, rec, run, session_id: str, rec_view: dict) -> None:
    """A rec that cleared earlier today has no live investigation. Its session
    opens by reading back what was resolved, once, through the same recorded
    tools a live session uses."""
    await ensure_session_row(s, rec, run, session_id, "recorded")
    has_calls = await s.scalar(
        select(SourceCall.call_id)
        .where(SourceCall.investigation_session_id == session_id)
        .limit(1)
    )
    if has_calls or not rec_view["adjustments"]:
        await s.commit()
        return
    tools = SessionTools(s, session_id, workspace(rec_view, run.business_date))
    await tools.breaks(rec_view["adjustments"])
    await tools.grounding(rec_view["adjustments"])
    await s.commit()


async def _messages(s, session_id: str) -> list[SessionMessage]:
    return (await s.scalars(
        select(SessionMessage)
        .where(SessionMessage.investigation_session_id == session_id)
        .order_by(SessionMessage.created_ts, SessionMessage.message_id)
    )).all()


async def message_view(s, m: SessionMessage, ccy: str) -> dict:
    out = {"id": m.message_id, "role": m.role, "time": ist_hhmm(m.created_ts)}
    if m.role == "agent":
        out["blocks"] = m.blocks or []
        out["calls"] = await calls_by_id(s, m.call_ids or [], ccy)
        out["answeredBy"] = m.answered_by
    else:
        out["text"] = m.text
    if m.tone:
        out["tone"] = m.tone
    return out


async def conversation(s, rec_view: dict) -> tuple[list[dict], list[dict]]:
    """The session's messages, and the analysis turn's calls."""
    sid = rec_view.get("sessionId")
    if not sid:
        return [], []
    stored = await _messages(s, sid)
    answered = {cid for m in stored for cid in (m.call_ids or [])}
    analysis_calls = [
        c for c in await session_calls(s, sid, rec_view["ccy"]) if c["id"] not in answered
    ]
    messages = []
    if rec_view["analysis"]:
        messages.append({
            "id": f"{rec_view['id']}-a0",
            "role": "agent",
            "kind": "analysis",
            "time": rec_view["updated"].replace(" IST", ""),
            "calls": analysis_calls,
        })
    for m in stored:
        messages.append(await message_view(s, m, rec_view["ccy"]))
    return messages, analysis_calls


async def add_message(s, session_id: str, role: str, *, text: str | None = None,
                      blocks: list | None = None, call_ids: list | None = None,
                      tone: str | None = None, answered_by: str | None = None) -> SessionMessage:
    m = SessionMessage(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        investigation_session_id=session_id,
        role=role,
        text=text,
        blocks=blocks,
        call_ids=call_ids,
        tone=tone,
        answered_by=answered_by,
        created_ts=datetime.now(timezone.utc),
    )
    s.add(m)
    await s.flush()
    return m
