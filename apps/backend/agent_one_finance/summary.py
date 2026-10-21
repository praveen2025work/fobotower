"""A task's Summary tab: what the run read, what it found, broken down the way the
agent's group says (`task.summarize_by`), what it proposes, and the model session
behind it — so a task that reconciles every book of a region at once (Rates EMEA,
about 300 books and 3,000 positions) can be read, and signed off, at the level of
desks and proposals rather than break by break."""

from collections import Counter, defaultdict

from sqlalchemy import select

from agent_one_finance import review, runner
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.models import Decision, ProposalGroup, Task, TaskItem, TaskMessage, ToolCall

SOURCE_STEPS = ("match", "load")         # the steps that read the task's data
MODEL_CALLERS = ("llm", "chat")
USAGE = ("input_tokens", "output_tokens", "cost_usd", "turns", "duration_ms")


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _money(values) -> dict:
    values = [_num(v) for v in values]
    return {"net": round(sum(values), 2), "gross": round(sum(abs(v) for v in values), 2)}


def _branch(items: list[dict], fields: list[str], amount: str | None, group_of: dict, decided: set) -> list[dict]:
    """The items broken down by `fields`, outermost first: one row per value with its
    counts and amounts, the proposals its items are in, and the rows a level down."""
    if not fields:
        return []
    field, rest = fields[0], fields[1:]
    by: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by[str(it.get(field) if it.get(field) is not None else "—")].append(it)
    out = []
    for value, members in by.items():
        proposals = Counter(group_of[it["item_id"]] for it in members if it["item_id"] in group_of)
        out.append({
            "field": field, "value": value, "items": len(members),
            **(_money(it.get(amount) for it in members) if amount else {}),
            "distinct": {f: len({str(it.get(f)) for it in members}) for f in rest},
            "proposals": [{"group_id": g, "items": n} for g, n in proposals.most_common()],
            "open": sum(1 for it in members if group_of.get(it["item_id"]) not in decided),
            "children": _branch(members, rest, amount, group_of, decided),
        })
    return sorted(out, key=lambda r: (-r.get("gross", 0), -r["items"], r["value"]))


def _sources(calls: list[ToolCall], fields: list[str], items: list[dict]) -> list[dict]:
    """Each read of the task's data: its tool, rows, and how many of each breakdown
    field it covered — e.g. 300 books read, 151 of them with nothing to explain."""
    out = []
    for c in calls:
        if c.requested_by not in SOURCE_STEPS or not c.allowed or c.error:
            continue
        rows = (c.result or {}).get("rows") if isinstance(c.result, dict) else None
        rows = rows if isinstance(rows, list) else []
        seen = {f: {str(r.get(f)) for r in rows if isinstance(r, dict) and r.get(f) is not None} for f in fields}
        seen = {f: v for f, v in seen.items() if v}
        with_items = {f: {str(it.get(f)) for it in items} for f in seen}
        out.append({"tool": c.tool, "step": c.requested_by, "arguments": c.arguments, "rows": c.row_count,
                    "distinct": {f: len(v) for f, v in seen.items()},
                    "without_items": {f: len(v - with_items[f]) for f, v in seen.items()}})
    return out


def _usage(rows: list[dict]) -> dict:
    total = {k: 0.0 for k in USAGE}
    known = set()
    for u in rows:
        for k in USAGE:
            if (u or {}).get(k) is not None:
                total[k] += _num(u[k])
                known.add(k)
    return {k: (round(v, 4) if k == "cost_usd" else int(v)) for k, v in total.items() if k in known}


def _model(task: Task, m, groups: list[ProposalGroup], calls: list[ToolCall], messages: list[TaskMessage]) -> dict:
    """Who decided what (rules, the playbook, the model), and the model's session:
    adapter and model, tokens, cost against the agent's limits, the lookups it made,
    the specialists it could hand work to, and a skill session if the agent ran one."""
    findings = [(g, g.finding or {}) for g in groups]
    by_model = [(g, f) for g, f in findings if str(f.get("decided_by", "")).startswith("llm")]
    lookups = [c for c in calls if c.requested_by in MODEL_CALLERS]
    session = (task.draft or {}).get("session")
    chat = [msg for msg in messages if msg.role == "assistant"]
    adapters = sorted({str(f["decided_by"]).split(":", 1)[1] for _, f in by_model if ":" in str(f["decided_by"])})
    models = sorted({str(f["model"]) for _, f in by_model if f.get("model")}
                    | ({str(session["model"])} if session and session.get("model") else set()))
    return {
        "decided_by": dict(Counter(str(f.get("decided_by", "none")).split(":", 1)[0] for _, f in findings)),
        "adapters": adapters or ([session["adapter"]] if session and session.get("adapter") else []),
        "models": models,
        "groups": [{"group_id": g.group_id, "label": g.label, "model": f.get("model"),
                    "status": f.get("status"), "reason": f.get("reason"),
                    **{k: (f.get("usage") or {}).get(k) for k in (*USAGE, "session_id")
                       if (f.get("usage") or {}).get(k) is not None}}
                   for g, f in by_model],
        "usage": _usage([f.get("usage") for _, f in by_model] + ([session] if session else [])),
        "chat": {"answers": len(chat), "usage": _usage([(msg.meta or {}).get("usage") for msg in chat])},
        "limits": {"max_cost_usd_per_task": m.limits.max_cost_usd_per_task,
                   "max_cost_usd_per_day": m.limits.max_cost_usd_per_day},
        "lookups": {"count": len(lookups), "refused": sum(1 for c in lookups if not c.allowed),
                    "by_tool": dict(Counter(c.tool for c in lookups))},
        "tools": list(m.reasoning.tools),
        "specialists": [{"name": sp.name, "description": sp.description, "tools": list(sp.tools)}
                        for sp in m.reasoning.specialists],
        "instructions_chars": len(m.reasoning.skill or ""),
        "skill_session": ({k: session.get(k) for k in ("adapter", "model", "skill_file", "turns", "cost_usd",
                                                        "duration_ms", "results", "failure", "session_id")
                           if session.get(k) is not None} if session else None),
    }


async def task_summary(task_id: str, caller: Caller) -> dict:
    from agent_one_finance.tasks import _latest, may_see_task

    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await runner.pinned(task)
        may_decide, _ = await review.acting_as(caller, m, task.task_key, may_see_task)
        if not may_see_task(caller, m, task.task_key) and not may_decide:
            raise LookupError(task_id)          # same answer as a missing task
        rows = (await s.execute(select(TaskItem).where(TaskItem.task_id == task_id))).scalars().all()
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.task_id == task_id)
                                  .order_by(ProposalGroup.group_id))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.task_id == task_id))).scalars().all()
        calls = (await s.execute(select(ToolCall).where(ToolCall.task_id == task_id)
                                 .order_by(ToolCall.called_at))).scalars().all()
        messages = (await s.execute(select(TaskMessage).where(TaskMessage.task_id == task_id))).scalars().all()
    amount = m.items.amount_field
    by = list(m.task.summarize_by or m.group_by)
    items = [{"item_id": r.item_id, **r.payload} for r in rows if not r.payload.get("excluded_by")]
    group_of = {i: g.group_id for g in groups for i in g.item_ids}
    latest = _latest(decisions)
    decided = set(latest)
    payload = {it["item_id"]: it for it in items}
    proposals = []
    for g in groups:
        f, members = g.finding or {}, [payload[i] for i in g.item_ids if i in payload]
        d = latest.get(g.group_id)
        proposals.append({
            "group_id": g.group_id, "label": g.label, "items": len(members),
            **(_money(it.get(amount) for it in members) if amount else {}),
            "distinct": {fld: len({str(it.get(fld)) for it in members}) for fld in by},
            "status": f.get("status"), "verdict": f.get("verdict"), "decided_by": f.get("decided_by"),
            "escalate_to": f.get("escalate_to"), "flags": review.flags(f),
            "decision": {"action": d.action, "by": d.decided_by, "at": d.decided_at} if d else None,
        })
    proposals.sort(key=lambda p: (-p.get("gross", 0), -p["items"]))
    return {
        "task_id": task.task_id, "subject": task.subject, "status": task.status, "outcome": task.outcome,
        "item_label": m.task.item_label, "unit": m.items.amount_unit, "amount_field": amount, "by": by,
        "sources": _sources(calls, by, items),
        "items": {"count": len(items), "in_proposals": sum(1 for it in items if it["item_id"] in group_of),
                  "open": sum(1 for it in items if group_of.get(it["item_id"]) not in decided),
                  **(_money(it.get(amount) for it in items) if amount else {}),
                  "distinct": {f: len({str(it.get(f)) for it in items}) for f in by}},
        "breakdown": _branch(items, by, amount, group_of, decided),
        "proposals": proposals,
        "model": _model(task, m, groups, calls, messages),
    }
