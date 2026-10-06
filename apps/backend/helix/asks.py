"""Asking for evidence instead of assuming it (FOBO skill §13).

A reviewer (or the controller at a tollgate) asks one of the capability's
`requests.targets` — the desk, a trader, Operations — a question about a group
or the whole case. The people addressed are notified and answer in Agent One Finance; a
bot (Teams, email) may answer for them through the API with the event secret.

While a question about a group is open, the group waits for it
(`requests.hold_decision`). The answer stays on the case, and reaches the model
as context whenever the group is investigated; during review it sends the
group back to the model (`requests.reinvestigate_on_answer`).
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from helix.db import get_session
from helix.entitlement import Caller
from helix.models import Case, InfoRequest, ProposalGroup

OPEN_STATUSES_FOR_ASKING = ("awaiting_review",)


class AskError(ValueError):
    pass


def _view(r: InfoRequest, caller: Caller | None = None) -> dict:
    out = {"request_id": r.request_id, "case_id": r.case_id, "group_id": r.group_id,
           "target": r.target, "target_name": r.target_name, "question": r.question,
           "asked_by": r.asked_by, "asked_at": r.asked_at, "status": r.status,
           "answer": r.answer, "answered_by": r.answered_by, "answered_at": r.answered_at,
           "attachment": ({"name": r.attachment, "url": f"/api/cases/{r.case_id}/evidence/{r.attachment}"}
                          if r.attachment else None),
           "reminded_at": r.reminded_at, "escalated_at": r.escalated_at}
    if caller is not None:
        out["can_answer"] = r.status == "open" and _addressed(r, caller)
    return out


def _addressed(r: InfoRequest, caller: Caller) -> bool:
    return caller.user_id in (r.users or []) or bool(set(r.roles or []) & caller.roles)


async def ask(case_id: str, target_id: str, question: str, group_id: str | None, caller: Caller) -> dict:
    from helix import cases, notify, review

    question = (question or "").strip()
    if not question:
        raise AskError("write the question")
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await cases._pinned(case)
        target = next((t for t in m.requests.targets if t.id == target_id), None)
        if target is None:
            raise AskError(f"no one called {target_id!r} to ask; this capability may ask: "
                           f"{', '.join(t.id for t in m.requests.targets) or 'no one'}")
        gate = cases.gate_step(case.status)
        may = ((await review.acting_as(caller, m, case.case_key, cases.may_see_case))[0]
               or (gate and cases.may_see_case(caller, m, case.case_key) and cases.may_pass_gate(caller, m, gate)))
        if not may:
            raise PermissionError(f"{caller.user_id} may not ask about this case")
        if case.status not in OPEN_STATUSES_FOR_ASKING and not gate:
            raise AskError(f"case is {case.status}; questions are asked while it is reviewed or at a tollgate")
        label = None
        if group_id is not None:
            group = await s.get(ProposalGroup, (case_id, group_id))
            if group is None:
                raise AskError(f"no group {group_id!r} in this case")
            label = group.label
        r = InfoRequest(request_id=uuid.uuid4().hex, case_id=case_id, group_id=group_id,
                        target=target.id, target_name=target.name, roles=list(target.roles),
                        users=list(target.users), question=question, asked_by=caller.user_id,
                        status="open")
        s.add(r)
        await s.commit()
        out = _view(r)
    await notify.send(capability_id=case.capability_id, case_id=case_id, kind="question",
                      title=f"Question from {caller.user_id}: {case.subject}" + (f" · {label}" if label else ""),
                      body=question[:500], roles=target.roles, users=target.users, extra=_bot_fields(r))
    return out


def _bot_fields(r: InfoRequest) -> dict:
    """What a Teams or email flow needs to collect the answer and post it back."""
    from helix.config import settings
    base = settings().console_url
    return {"request_id": r.request_id, "question": r.question, "target": r.target,
            "answer_url": f"{base}/api/requests/{r.request_id}/answer",
            "answer_with_file_url": f"{base}/api/requests/{r.request_id}/answer-with-file",
            "answer_in_console": f"{base}/inbox"}


async def answer(request_id: str, text: str, caller: Caller | None, on_behalf: str | None = None,
                 file: tuple[str, bytes] | None = None) -> dict:
    """An addressee answers (caller), or a bot answers for someone (on_behalf,
    with the event secret checked by the route). A file sent with the answer
    (requests.allow_attachments) is kept as the case's evidence."""
    from helix import cases, evidence, notify

    text = (text or "").strip()
    if not text:
        raise AskError("write the answer")
    async with get_session() as s:
        r = await s.get(InfoRequest, request_id)
        if r is None:
            raise LookupError(request_id)
        if caller is not None and not _addressed(r, caller):
            raise PermissionError(f"this question is for {r.target_name}")
        if r.status != "open":
            raise AskError(f"this question is {r.status}")
        case = await s.get(Case, r.case_id)
        m = await cases._pinned(case)
        who = caller.user_id if caller is not None else (on_behalf or "bot")
        if file is not None:
            if not m.requests.allow_attachments:
                raise AskError("answers to this capability's questions cannot carry files")
            try:
                saved = await evidence.store(case, file[0], file[1],
                                             f"{r.target_name} ({who}), answering: {r.question}"[:500], who)
            except cases.CaseError as e:
                raise AskError(str(e)) from None
            r.attachment = saved["name"]
        r.status, r.answer = "answered", text
        r.answered_by = who
        r.answered_at = datetime.now(timezone.utc)
        await s.commit()
        out = _view(r)
    await notify.send(capability_id=case.capability_id, case_id=case.case_id, kind="answered",
                      title=f"{r.target_name} answered: {case.subject}", body=text[:500], users=[r.asked_by])
    if (r.group_id and m.requests.reinvestigate_on_answer and case.status == "awaiting_review"
            and m.reasoning.reasoner == "llm"):
        from helix.entitlement import entitlements
        try:   # back to the model with the answer, as the person who asked
            await cases.reinvestigate(case.case_id, r.group_id,
                                      f"{r.target_name} ({r.answered_by}) answered \"{r.question}\": {text}",
                                      f"answer:{r.request_id}", await entitlements().get(r.asked_by))
            out["reinvestigated"] = True
        except (cases.CaseError, PermissionError) as e:   # e.g. the send-back limit: the answer still stands
            out["reinvestigated"] = False
            out["not_reinvestigated_because"] = str(e)
    return out


async def cancel(request_id: str, caller: Caller) -> dict:
    from helix import cases, review

    async with get_session() as s:
        r = await s.get(InfoRequest, request_id)
        if r is None:
            raise LookupError(request_id)
        case = await s.get(Case, r.case_id)
        m = await cases._pinned(case)
        if caller.user_id != r.asked_by and not (await review.acting_as(
                caller, m, case.case_key, cases.may_see_case))[0]:
            raise PermissionError("only whoever asked, or a reviewer, cancels a question")
        if r.status != "open":
            raise AskError(f"this question is {r.status}")
        r.status = "cancelled"
        await s.commit()
        return _view(r)


async def for_case(case_id: str, caller: Caller) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(InfoRequest).where(InfoRequest.case_id == case_id)
                                .order_by(InfoRequest.asked_at))).scalars().all()
    return [_view(r, caller) for r in rows]


async def open_on_group(case_id: str, group_id: str) -> list[InfoRequest]:
    async with get_session() as s:
        return (await s.execute(select(InfoRequest).where(
            InfoRequest.case_id == case_id, InfoRequest.group_id == group_id,
            InfoRequest.status == "open"))).scalars().all()


async def answers_for(case_id: str, group_id: str | None) -> list[str]:
    """Answered questions about this group or the whole case, as model context."""
    async with get_session() as s:
        rows = (await s.execute(select(InfoRequest).where(
            InfoRequest.case_id == case_id, InfoRequest.status == "answered")
            .order_by(InfoRequest.answered_at))).scalars().all()
    return [f"{r.target_name} ({r.answered_by}) answered \"{r.question}\": {r.answer}"
            + (f" (attached: {r.attachment}, in the case's documents)" if r.attachment else "")
            for r in rows if r.group_id in (None, group_id)]


async def mine(caller: Caller) -> list[dict]:
    """Open questions addressed to the caller, with just enough to answer them:
    the case, the group and its rows — not the whole case."""
    from helix import cases

    async with get_session() as s:
        rows = (await s.execute(select(InfoRequest).where(InfoRequest.status == "open")
                                .order_by(InfoRequest.asked_at))).scalars().all()
        out = []
        for r in rows:
            if not _addressed(r, caller):
                continue
            case = await s.get(Case, r.case_id)
            m = await cases._pinned(case)
            group = await s.get(ProposalGroup, (r.case_id, r.group_id)) if r.group_id else None
            items = []
            if group is not None:
                from helix.models import CaseItem
                items = [i.payload for i in (await s.execute(select(CaseItem).where(
                    CaseItem.case_id == r.case_id, CaseItem.item_id.in_(group.item_ids)))).scalars()]
            columns = m.items.display or sorted({k for i in items for k in i})
            out.append({**_view(r, caller), "subject": case.subject, "case_label": m.case.label,
                        "group_label": group.label if group else None, "columns": columns,
                        "rows": [{c: i.get(c) for c in columns} for i in items]})
    return out


async def chase(now: datetime | None = None) -> list[tuple[str, str]]:
    """Unanswered questions: remind the people asked after
    requests.remind_after_hours, and tell the reviewers and whoever asked after
    requests.escalate_after_hours. Each happens once per question. Run by the
    scheduler every minute, like deadline reminders."""
    from helix import cases, notify

    now = now or datetime.now(timezone.utc)
    done = []
    async with get_session() as s:
        rows = (await s.execute(select(InfoRequest).where(InfoRequest.status == "open"))).scalars().all()
        for r in rows:
            case = await s.get(Case, r.case_id)
            m = await cases._pinned(case)
            spec = m.requests
            age = now - r.asked_at
            if (spec.escalate_after_hours and r.escalated_at is None
                    and age >= timedelta(hours=spec.escalate_after_hours)):
                r.escalated_at = now
                await notify.send(capability_id=case.capability_id, case_id=case.case_id, kind="question_unanswered",
                                  title=f"Unanswered for {spec.escalate_after_hours:g}h: {r.target_name} · {case.subject}",
                                  body=r.question[:500], roles=list(m.review.roles), users=[r.asked_by])
                done.append((r.request_id, "escalated"))
            elif (spec.remind_after_hours and r.reminded_at is None
                    and age >= timedelta(hours=spec.remind_after_hours)):
                r.reminded_at = now
                await notify.send(capability_id=case.capability_id, case_id=case.case_id, kind="question_reminder",
                                  title=f"Reminder — question from {r.asked_by}: {case.subject}",
                                  body=r.question[:500], roles=r.roles, users=r.users, extra=_bot_fields(r))
                done.append((r.request_id, "reminded"))
        await s.commit()
    return done
