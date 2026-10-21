"""Insights across tasks: items that keep coming back.

Configured by `insights.recurring` in the manifest (agent or group):

    insights:
      recurring:
        same: [book]          # task-key fields that must match: the same book, earlier COBs
        lookback_tasks: 10    # how many earlier runs to look at
        min_runs: 2           # flagged when seen in at least this many runs, this one included

An item recurs when the same item id was in a reviewed group (in scope) of
an earlier task of the same agent and team group whose `same` fields
match. Re-runs of one key count once. Only tasks the caller may see count
on the agent-wide list.
"""

import itertools

from sqlalchemy import select

from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Task, ProposalGroup


def _key_of(c: Task) -> str:
    return c.root_task_id or c.task_id


async def _in_scope_items(s, task_ids: list[str]) -> dict[str, set[str]]:
    rows = (await s.execute(select(ProposalGroup.task_id, ProposalGroup.item_ids).where(
        ProposalGroup.task_id.in_(task_ids)))).all() if task_ids else []
    out: dict[str, set[str]] = {}
    for task_id, item_ids in rows:
        out.setdefault(task_id, set()).update(item_ids or [])
    return out


async def recurring_for_task(task: Task, m: Manifest, item_ids: list[str]) -> dict[str, dict]:
    """item_id -> {runs, earlier: [{task_id, subject, opened_at}]} for this task's items."""
    spec = m.insights.recurring
    if not spec or not item_ids:
        return {}
    async with get_session() as s:
        q = select(Task).where(Task.agent_id == task.agent_id, Task.shadow_of.is_(None),
                               Task.task_id != task.task_id, Task.opened_at < task.opened_at)
        q = q.where(Task.team_group == task.team_group) if task.team_group else q.where(Task.team_group.is_(None))
        for f in spec.same:
            q = q.where(Task.task_key[f].astext == str(task.task_key.get(f)))
        earlier = [c for c in (await s.execute(q.order_by(Task.opened_at.desc()).limit(
            spec.lookback_tasks * 3))).scalars() if _key_of(c) != _key_of(task)]
        # one run per task key (the latest attempt), newest first
        runs: dict[str, Task] = {}
        for c in earlier:
            k = str(sorted(c.task_key.items()))
            if k not in runs and str(sorted(c.task_key.items())) != str(sorted(task.task_key.items())):
                runs[k] = c
        runs_list = list(runs.values())[:spec.lookback_tasks]
        seen = await _in_scope_items(s, [c.task_id for c in runs_list])
    out = {}
    for item_id in item_ids:
        hits = [c for c in runs_list if item_id in seen.get(c.task_id, set())]
        if len(hits) + 1 >= spec.min_runs:
            out[item_id] = {"runs": len(hits) + 1,
                            "earlier": [{"task_id": c.task_id, "subject": c.subject,
                                         "opened_at": c.opened_at} for c in hits]}
    return out


async def recurring_overview(agent_id: str, caller: Caller, team_group: str | None,
                             limit_tasks: int = 300) -> list[dict]:
    """Items recurring across the caller's visible tasks of an agent (or
    group), most frequent first, by the group's `same` fields."""
    from agent_one_finance.tasks import visible_tasks

    rows = await visible_tasks(caller, agent_id=agent_id, team_group=team_group,
                               limit=limit_tasks)
    rows = [(c, m) for c, m in rows if m.insights.recurring]
    if not rows:
        return []
    latest: dict[str, tuple[Task, Manifest]] = {}
    for c, m in rows:                                 # newest first: keep the latest attempt per key
        latest.setdefault(str(sorted(c.task_key.items())) + (c.team_group or ""), (c, m))
    async with get_session() as s:
        seen = await _in_scope_items(s, [c.task_id for c, _ in latest.values()])
    tally: dict[tuple, dict] = {}
    for c, m in latest.values():
        same = tuple((f, c.task_key.get(f)) for f in m.insights.recurring.same)
        for item_id in seen.get(c.task_id, set()):
            t = tally.setdefault((c.team_group, same, item_id), {
                "item_id": item_id, "team_group": c.team_group, "same": dict(same),
                "runs": 0, "latest_task_id": c.task_id, "latest_subject": c.subject,
                "min_runs": m.insights.recurring.min_runs})
            t["runs"] += 1
    out = [t for t in tally.values() if t["runs"] >= t["min_runs"]]
    return sorted(out, key=lambda t: (-t["runs"], t["item_id"]))[:100]


# ---------- what nothing explained, and what could be a rule ----------

def _latest_decisions(decisions) -> dict[tuple[str, str], object]:
    out = {}
    for d in sorted(decisions, key=lambda d: d.decided_at):
        out[(d.task_id, d.group_id)] = d
    return out


async def learning(agent_id: str, caller: Caller, team_group: str | None,
                   limit_tasks: int = 500) -> dict:
    """Two lists for whoever owns the playbook or the rules:

    unexplained  items nothing explained (insights.unexplained): with a
                 playbook, no cause check was positive or the category is one
                 listed (e.g. FOBO's H Novel); without one, the group was
                 escalated because neither a rule nor the model settled it.
    automation   groups the model proposed that reviewers approved unchanged
                 at least `insights.automation_after` times and never
                 rejected — e.g. FOBO's aged breaks on one side, or one
                 variance account's commentary — candidates for a rule or a
                 deterministic category.
    Only the caller's visible tasks count; re-runs of one key count once."""
    from datetime import datetime, timedelta, timezone

    from agent_one_finance.tasks import visible_tasks
    from agent_one_finance.models import TaskItem, Decision

    rows = await visible_tasks(caller, agent_id=agent_id, team_group=team_group, limit=limit_tasks)
    latest: dict[str, tuple[Task, Manifest]] = {}
    for c, m in rows:
        latest.setdefault(str(sorted(c.task_key.items())) + (c.team_group or "") + (c.follow_up_of or ""), (c, m))
    if not latest:
        return {"unexplained": [], "unexplained_by_reason": [], "automation": [], "proposed_checks": []}
    ids = [c.task_id for c, _ in latest.values()]
    async with get_session() as s:
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.task_id.in_(ids)))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.task_id.in_(ids)))).scalars().all()
        items = {(i.task_id, i.item_id): i.payload for i in (await s.execute(
            select(TaskItem).where(TaskItem.task_id.in_(ids)))).scalars()}
    by_task = {c.task_id: (c, m) for c, m in latest.values()}
    decided = _latest_decisions(decisions)
    now = datetime.now(timezone.utc)

    unexplained, tally = [], {}
    auto: dict[tuple, dict] = {}
    examples: list[dict] = []
    needed = 5
    for g in groups:
        c, m = by_task[g.task_id]
        f = g.finding or {}
        spec = m.insights.unexplained
        if spec and c.opened_at >= now - timedelta(days=spec.lookback_days):
            for item_id in g.item_ids:
                it = items.get((g.task_id, item_id), {})
                if m.playbook:
                    why = ("no cause check explained it" if it.get("category") is not None and not it.get("cause")
                           else f"{it.get('category')} · {it.get('category_name')}"
                           if it.get("category") in spec.categories else None)
                else:
                    why = (f.get("reason") or "escalated") if (
                        f.get("status") == "escalated" and f.get("decided_by") != "rule") else None
                if why:
                    unexplained.append({"task_id": c.task_id, "subject": c.subject, "team_group": c.team_group,
                                        "item_id": item_id, "group": g.label, "why": why,
                                        "amount": it.get(m.items.amount_field) if m.items.amount_field else None,
                                        "opened_at": c.opened_at})
                    tally[why] = tally.get(why, 0) + 1
        if not str(f.get("decided_by", "")).startswith("llm"):
            continue
        d = decided.get((g.task_id, g.group_id))
        if d is None:
            continue
        needed = m.insights.automation_after
        if d.action == "approve":
            for item_id in g.item_ids:
                it = items.get((g.task_id, item_id), {})
                examples.append({"scope": (c.team_group, it.get("category") or g.label),
                                 "row": it, "label": f.get("verdict") or f.get("status") or "approved",
                                 "task": c.subject})
        key = (c.team_group, tuple(sorted(g.group_key.items())), f.get("verdict"))
        a = auto.setdefault(key, {"team_group": c.team_group, "group_key": dict(g.group_key), "label": g.label,
                                  "verdict": f.get("verdict"), "approved": 0, "rejected": 0,
                                  "needed": m.insights.automation_after, "tasks": []})
        if d.action == "approve":
            a["approved"] += 1
        else:
            a["rejected"] += 1
        a["tasks"].append(c.subject)
    automation = sorted((dict(a, tasks=a["tasks"][:5]) for a in auto.values()
                         if a["approved"] >= a["needed"] and a["rejected"] == 0),
                        key=lambda a: -a["approved"])
    unexplained.sort(key=lambda r: r["opened_at"], reverse=True)
    return {"proposed_checks": propose_checks(examples, needed)[:30],
            "unexplained": unexplained[:200],
            "unexplained_by_reason": sorted(({"why": k, "items": v} for k, v in tally.items()),
                                            key=lambda r: -r["items"]),
            "automation": automation[:50]}


# ---------------------------------------------------------------------
# Proposed checks: a condition on the data that predicts the verdict
# ---------------------------------------------------------------------

# Fields the playbook or the platform wrote: they describe the outcome, not the break.
_NOT_FEATURES = {"item_id", "checks", "tests", "test_finding", "blocked_by", "cause_reason", "category",
                 "category_name", "determinism", "escalate_to", "cause", "excluded_by", "excluded_reason"}
MIN_PRECISION = 0.95


def _fmt(v) -> str:
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return f"{v:g}" if isinstance(v, float) else str(v)


def _conditions(rows: list[dict]) -> list[tuple[str, object]]:
    """Candidate conditions over the rows' own fields: a flag, a value of a
    field with few values, or a threshold of a number. Each is (expression,
    test) where test(row) -> bool."""
    fields: dict[str, list] = {}
    for r in rows:
        for k, v in r.items():
            if k in _NOT_FEATURES or k.endswith(("_candidates", "_members", "_where", "_reasons", "_at", "_ts")):
                continue
            if isinstance(v, (bool, int, float, str)) or v is None:
                fields.setdefault(k, []).append(v)
    out: list[tuple[str, object]] = []
    for k, vals in sorted(fields.items()):
        present = [v for v in vals if v is not None]
        if not present:
            continue
        if all(isinstance(v, bool) for v in present):
            out.append((k, lambda r, k=k: r.get(k) is True))
            out.append((f"not {k}", lambda r, k=k: r.get(k) is False))
        elif all(isinstance(v, str) for v in present):
            distinct = sorted(set(present))
            if 1 < len(distinct) <= 12:
                out += [(f"{k} == {_fmt(v)}", lambda r, k=k, v=v: r.get(k) == v) for v in distinct]
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
            distinct = sorted(set(present))
            if len(distinct) < 2:
                continue
            step = max(1, len(distinct) // 20)
            cuts = [(a + b) / 2 for a, b in zip(distinct[::step], distinct[step::step])]
            cuts = [round(c, 2) if abs(c) < 1000 else round(c) for c in cuts]
            for c in dict.fromkeys(cuts):
                out.append((f"{k} >= {_fmt(c)}", lambda r, k=k, c=c: isinstance(r.get(k), (int, float)) and r.get(k) >= c))
                out.append((f"{k} < {_fmt(c)}", lambda r, k=k, c=c: isinstance(r.get(k), (int, float)) and r.get(k) < c))
    return out


def propose_checks(examples: list[dict], needed: int) -> list[dict]:
    """examples: [{"scope": (team_group, category), "row": item fields, "label":
    the verdict people approved, "task": subject}]. For each scope where people
    approved more than one verdict, the simplest condition (one, else two
    joined by `and`) that picks out one verdict with at least 95% precision
    and at least `needed` tasks. A proposal for the playbook's owners, who
    replay it before anything changes."""
    by_scope: dict[tuple, list[dict]] = {}
    for e in examples:
        by_scope.setdefault(e["scope"], []).append(e)
    out = []
    for scope, ex in sorted(by_scope.items(), key=lambda kv: str(kv[0])):
        labels = sorted({e["label"] for e in ex})
        if len(labels) < 2:
            continue                           # one verdict only: the automation list already says so
        conds = _conditions([e["row"] for e in ex])
        for label in labels:
            pos = [e for e in ex if e["label"] == label]
            if len(pos) < needed:
                continue

            def score(test):
                hit = [e for e in ex if test(e["row"])]
                tp = sum(1 for e in hit if e["label"] == label)
                return tp, len(hit) - tp

            singles = []
            for expr, test in conds:
                tp, fp = score(test)
                if tp >= needed:
                    singles.append((tp / (tp + fp), tp, -len(expr), expr, test, fp))
            best = max((c for c in singles if c[0] >= MIN_PRECISION), default=None)
            if best is None:
                top = sorted(singles, reverse=True)[:15]
                pairs = []
                for (_, _, _, e1, t1, _), (_, _, _, e2, t2, _) in itertools.combinations(top, 2):
                    tp, fp = score(lambda r, t1=t1, t2=t2: t1(r) and t2(r))
                    if tp >= needed and tp / (tp + fp) >= MIN_PRECISION:
                        pairs.append((tp / (tp + fp), tp, -len(e1 + e2), f"{e1} and {e2}", None, fp))
                best = max(pairs, default=None)
            if best is None:
                continue
            precision, tp, _, expr, _, fp = best
            out.append({"team_group": scope[0], "category": scope[1], "verdict": label, "when": expr,
                        "covers": tp, "of": len(pos), "wrong": fp, "precision": round(precision, 3),
                        "tasks": sorted({e["task"] for e in pos})[:3]})
    return sorted(out, key=lambda p: (-p["covers"], p["when"]))
