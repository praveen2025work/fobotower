"""Ask about a case, and see how its run went.

Ask: anyone who can see a case may ask about it in plain words ("why is
6300 different?"). The model answers from the case — its groups, findings
and items — and may call the capability's read tools through the gateway,
so every lookup is allowed-listed, scoped and audited like any other. The
answer's figures are checked against what the run (and the answer's own
tool calls) read; untraceable figures are listed with the answer, never
hidden. Masked and pseudonymized fields stay protected from the model.

History: the case's LangGraph checkpoints, step by step — when each step
ran, how long it took, what it left behind, and where people stepped in.
Any point can be opened to see the state exactly as it was.
"""

import uuid

from sqlalchemy import select

from helix import controls, gateway, runner, steps
from helix.cases import CaseError, case_detail, may_see_case
from helix.db import get_session
from helix.entitlement import Caller
from helix.governance import Protector
from helix.llm import AskRequest, llm
from helix.models import Case, CaseMessage
from helix.observability import span
from helix.workflow import build_graph, checkpointer

MAX_QUESTION = 4000


class _RecordOnly:
    """Over the spend limit: answer from the case's record, no model."""
    name = "none"

    def __init__(self, why: str):
        self.why = why

    async def ask(self, request, tools):
        from helix.llm import AskResult, _from_case
        return AskResult(answer=f"{_from_case(request)} (No model: {self.why}.)")


async def _case(case_id: str, caller: Caller) -> tuple[Case, object]:
    async with get_session() as s:
        case = await s.get(Case, case_id)
    if case is None:
        raise LookupError(case_id)
    m = await runner.pinned(case)
    if not may_see_case(caller, m, case.case_key):
        raise LookupError(case_id)
    return case, m


def _message(r: CaseMessage) -> dict:
    return {"message_id": r.message_id, "role": r.role, "author": r.author, "text": r.text,
            "meta": r.meta, "created_at": r.created_at}


async def messages(case_id: str, caller: Caller) -> list[dict]:
    await _case(case_id, caller)
    async with get_session() as s:
        rows = (await s.execute(select(CaseMessage).where(CaseMessage.case_id == case_id)
                                .order_by(CaseMessage.created_at, CaseMessage.message_id))).scalars().all()
    return [_message(r) for r in rows]


async def ask(case_id: str, question: str, caller: Caller) -> dict:
    question = (question or "").strip()
    if not question:
        raise CaseError("ask a question")
    if len(question) > MAX_QUESTION:
        raise CaseError(f"a question is at most {MAX_QUESTION} characters")
    case, m = await _case(case_id, caller)
    detail = await case_detail(case_id, caller)
    async with get_session() as s:
        s.add(CaseMessage(message_id=uuid.uuid4().hex, case_id=case_id, role="user",
                          author=caller.user_id, text=question, meta={}))
        await s.commit()
        history = (await s.execute(select(CaseMessage).where(CaseMessage.case_id == case_id)
                                   .order_by(CaseMessage.created_at).limit(20))).scalars().all()

    guard = Protector.for_tools(m.tools_used(), case_id)
    ctx = gateway.CallContext(capability_id=case.capability_id, caller=caller,
                              allowed_tools=frozenset(m.reasoning.tools), case_id=case_id,
                              requested_by="chat", protector=guard)
    context = {
        "subject": case.subject, "status": case.status, "headline": (case.draft or {}).get("headline"),
        "groups": [{"group_id": g["group_id"], "label": g["label"], "group_key": g["group_key"],
                    "finding": {k: (g["finding"] or {}).get(k) for k in
                                ("status", "comment", "reason", "verdict", "category_name",
                                 "escalate_to", "requires_confirmation")},
                    "decision": g["decision"], "items": g["item_ids"]} for g in detail["groups"]],
        "items": detail["items"][:200],
    }
    # Field-level protection, then every protected value the case knows about
    # scrubbed out of free text (labels, comments, the question itself).
    known = [case.case_key, *[g["group_key"] for g in detail["groups"]], *detail["items"]]
    request = AskRequest(
        capability_id=case.capability_id, case_id=case_id,
        case_key=guard.scrub(guard.protect(case.case_key), known), skill=m.reasoning.skill,
        question=guard.scrub(question, known),
        context=guard.scrub(guard.protect(context), known),
        history=[{"role": h.role, "text": guard.scrub(h.text, known)} for h in history[:-1]],
        allowed_tools=list(m.reasoning.tools))
    adapter = llm()
    if over := await controls.over_budget(m, case_id):
        adapter = _RecordOnly(over)
    with span("case.ask", root=True, case_id=case_id, capability_id=case.capability_id,
              user=caller.user_id) as sp:
        before = len(ctx.calls)
        try:
            res = await adapter.ask(request, gateway.invoker(ctx, "chat"))
            text, model, usage = guard.reveal(res.answer), res.model, res.usage
        except Exception as e:  # an unanswerable question is an answer, not a 500
            text, model, usage = f"I could not answer that: {type(e).__name__}: {e}", None, {}
        sp.set_attribute("helix.tool_calls", len(ctx.calls) - before)
    state = {"case_key": case.case_key, "items": detail["items"],
             "groups": [{**g, "finding": g["finding"]} for g in detail["groups"]], "case_id": case_id}
    unverified = steps.ungrounded(text, await steps.grounded_figures(state))
    meta = {"model": model, "usage": usage, "tool_calls": ctx.calls[before:],
            "unverified_figures": unverified}
    async with get_session() as s:
        answer = CaseMessage(message_id=uuid.uuid4().hex, case_id=case_id, role="assistant",
                             author=f"llm:{adapter.name}", text=text, meta=meta)
        s.add(answer)
        await s.commit()
    return {"answer": {"role": "assistant", "author": answer.author, "text": text, "meta": meta},
            "messages": await messages(case_id, caller)}


# ---------- history ----------

async def history(case_id: str, caller: Caller) -> list[dict]:
    """The run, oldest first: each step with its start, end and what it left;
    each human input (decisions, release) where it came in."""
    case, m = await _case(case_id, caller)
    config = {"configurable": {"thread_id": f"helix:{case_id}"}}
    async with checkpointer() as cp:
        app = build_graph(m.steps, m.pause_before, cp, m.step_types())
        snaps = [s async for s in app.aget_state_history(config)]
    snaps.reverse()
    out = []
    for i, snap in enumerate(snaps):
        meta = snap.metadata or {}
        nxt = list(snap.next)
        following = snaps[i + 1] if i + 1 < len(snaps) else None
        # what the run held once this step was done (or now, for a pause)
        values = (following.values if following is not None else snap.values) or {}
        entry = {"checkpoint_id": snap.config["configurable"].get("checkpoint_id"),
                 "at": snap.created_at, "source": meta.get("source"), "next": nxt,
                 "items": len(values.get("items", []) or []),
                 "groups": len(values.get("groups", []) or []),
                 "findings": len(values.get("findings", {}) or {})}
        if meta.get("source") == "update":
            writes = sorted(set(values) & {"decisions", "publish_approval", "findings"})
            entry["event"] = "people"
            entry["step"] = "input: " + (", ".join(writes) or "update")
        elif nxt and following is not None:
            entry["event"] = "step"
            entry["step"] = nxt[0]
            entry["ended_at"] = following.created_at
        elif nxt:
            entry["event"] = "waiting"
            entry["step"] = nxt[0]
        else:
            entry["event"] = "end"
            entry["step"] = "end"
        if meta.get("source") == "input":
            entry["event"], entry["step"] = "start", "start"
        out.append(entry)
    return out


async def state_at(case_id: str, checkpoint_id: str, caller: Caller) -> dict:
    """The run's state exactly as it was at one checkpoint."""
    case, m = await _case(case_id, caller)
    config = {"configurable": {"thread_id": f"helix:{case_id}", "checkpoint_id": checkpoint_id}}
    async with checkpointer() as cp:
        snap = await build_graph(m.steps, m.pause_before, cp, m.step_types()).aget_state(config)
    if snap.created_at is None:
        raise LookupError(f"{case_id}@{checkpoint_id}")
    v = snap.values or {}
    return {"checkpoint_id": checkpoint_id, "at": snap.created_at, "next": list(snap.next),
            "items": v.get("items", []), "groups": v.get("groups", []),
            "findings": v.get("findings", {}), "decisions": v.get("decisions", []),
            "publish_approval": v.get("publish_approval"), "outcome": v.get("outcome")}
