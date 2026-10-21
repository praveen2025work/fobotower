"""Ask about a task, and see how its run went.

Ask: anyone who can see a task may ask about it in plain words ("why is
6300 different?"). The model answers from the task — its groups, findings
and items — and may call the agent's read tools through the gateway,
so every lookup is allowed-listed, scoped and audited like any other. The
answer's figures are checked against what the run (and the answer's own
tool calls) read; untraceable figures are listed with the answer, never
hidden. Masked and pseudonymized fields stay protected from the model.

History: the task's LangGraph checkpoints, step by step — when each step
ran, how long it took, what it left behind, and where people stepped in.
Any point can be opened to see the state exactly as it was.
"""

import uuid

from sqlalchemy import select

from agent_one_finance import controls, gateway, runner, steps
from agent_one_finance.tasks import TaskError, task_detail, may_see_task
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.governance import Protector
from agent_one_finance.llm import AskRequest, llm
from agent_one_finance.models import Task, TaskMessage
from agent_one_finance.observability import span
from agent_one_finance.workflow import build_graph, checkpointer

MAX_QUESTION = 4000


class _RecordOnly:
    """Over the spend limit: answer from the task's record, no model."""
    name = "none"

    def __init__(self, why: str):
        self.why = why

    async def ask(self, request, tools):
        from agent_one_finance.llm import AskResult, _from_task
        return AskResult(answer=f"{_from_task(request)} (No model: {self.why}.)")


async def _task(task_id: str, caller: Caller) -> tuple[Task, object]:
    async with get_session() as s:
        task = await s.get(Task, task_id)
    if task is None:
        raise LookupError(task_id)
    m = await runner.pinned(task)
    if not may_see_task(caller, m, task.task_key):
        raise LookupError(task_id)
    return task, m


def _message(r: TaskMessage) -> dict:
    return {"message_id": r.message_id, "role": r.role, "author": r.author, "text": r.text,
            "meta": r.meta, "created_at": r.created_at}


async def messages(task_id: str, caller: Caller) -> list[dict]:
    await _task(task_id, caller)
    async with get_session() as s:
        rows = (await s.execute(select(TaskMessage).where(TaskMessage.task_id == task_id)
                                .order_by(TaskMessage.created_at, TaskMessage.message_id))).scalars().all()
    return [_message(r) for r in rows]


async def ask(task_id: str, question: str, caller: Caller) -> dict:
    question = (question or "").strip()
    if not question:
        raise TaskError("ask a question")
    if len(question) > MAX_QUESTION:
        raise TaskError(f"a question is at most {MAX_QUESTION} characters")
    task, m = await _task(task_id, caller)
    detail = await task_detail(task_id, caller)
    async with get_session() as s:
        s.add(TaskMessage(message_id=uuid.uuid4().hex, task_id=task_id, role="user",
                          author=caller.user_id, text=question, meta={}))
        await s.commit()
        history = (await s.execute(select(TaskMessage).where(TaskMessage.task_id == task_id)
                                   .order_by(TaskMessage.created_at).limit(20))).scalars().all()

    guard = Protector.for_tools(m.tools_used(), task_id)
    ctx = gateway.CallContext(agent_id=task.agent_id, caller=caller,
                              allowed_tools=frozenset(m.reasoning.tools), task_id=task_id,
                              requested_by="chat", protector=guard)
    context = {
        "subject": task.subject, "status": task.status, "headline": (task.draft or {}).get("headline"),
        "groups": [{"group_id": g["group_id"], "label": g["label"], "group_key": g["group_key"],
                    "finding": {k: (g["finding"] or {}).get(k) for k in
                                ("status", "comment", "reason", "verdict", "category_name",
                                 "escalate_to", "requires_confirmation")},
                    "decision": g["decision"], "items": g["item_ids"]} for g in detail["groups"]],
        "items": detail["items"][:200],
    }
    # Field-level protection, then every protected value the task knows about
    # scrubbed out of free text (labels, comments, the question itself).
    known = [task.task_key, *[g["group_key"] for g in detail["groups"]], *detail["items"]]
    request = AskRequest(
        agent_id=task.agent_id, task_id=task_id,
        task_key=guard.scrub(guard.protect(task.task_key), known), skill=m.reasoning.skill,
        question=guard.scrub(question, known),
        context=guard.scrub(guard.protect(context), known),
        history=[{"role": h.role, "text": guard.scrub(h.text, known)} for h in history[:-1]],
        allowed_tools=list(m.reasoning.tools))
    adapter = llm()
    if over := await controls.over_budget(m, task_id):
        adapter = _RecordOnly(over)
    with span("task.ask", root=True, task_id=task_id, agent_id=task.agent_id,
              user=caller.user_id) as sp:
        before = len(ctx.calls)
        try:
            res = await adapter.ask(request, gateway.invoker(ctx, "chat"))
            text, model, usage = guard.reveal(res.answer), res.model, res.usage
        except Exception as e:  # an unanswerable question is an answer, not a 500
            text, model, usage = f"I could not answer that: {type(e).__name__}: {e}", None, {}
        sp.set_attribute("aof.tool_calls", len(ctx.calls) - before)
    state = {"task_key": task.task_key, "items": detail["items"],
             "groups": [{**g, "finding": g["finding"]} for g in detail["groups"]], "task_id": task_id}
    unverified = steps.ungrounded(text, await steps.grounded_figures(state))
    meta = {"model": model, "usage": usage, "tool_calls": ctx.calls[before:],
            "unverified_figures": unverified}
    async with get_session() as s:
        answer = TaskMessage(message_id=uuid.uuid4().hex, task_id=task_id, role="assistant",
                             author=f"llm:{adapter.name}", text=text, meta=meta)
        s.add(answer)
        await s.commit()
    return {"answer": {"role": "assistant", "author": answer.author, "text": text, "meta": meta},
            "messages": await messages(task_id, caller)}


# ---------- history ----------

async def history(task_id: str, caller: Caller) -> list[dict]:
    """The run, oldest first: each step with its start, end and what it left;
    each human input (decisions, release) where it came in."""
    task, m = await _task(task_id, caller)
    config = {"configurable": {"thread_id": f"aof:{task_id}"}}
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


async def state_at(task_id: str, checkpoint_id: str, caller: Caller) -> dict:
    """The run's state exactly as it was at one checkpoint."""
    task, m = await _task(task_id, caller)
    config = {"configurable": {"thread_id": f"aof:{task_id}", "checkpoint_id": checkpoint_id}}
    async with checkpointer() as cp:
        snap = await build_graph(m.steps, m.pause_before, cp, m.step_types()).aget_state(config)
    if snap.created_at is None:
        raise LookupError(f"{task_id}@{checkpoint_id}")
    v = snap.values or {}
    return {"checkpoint_id": checkpoint_id, "at": snap.created_at, "next": list(snap.next),
            "items": v.get("items", []), "groups": v.get("groups", []),
            "findings": v.get("findings", {}), "decisions": v.get("decisions", []),
            "publish_approval": v.get("publish_approval"), "outcome": v.get("outcome")}
