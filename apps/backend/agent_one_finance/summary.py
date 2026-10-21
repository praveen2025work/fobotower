"""An agent's day at a glance, for when there are too many tasks to open one by one.

With a task per master book, a COB is 1,000–2,000 tasks. Controllers do not
work them individually: they look at the day by business, region, desk or
product, see the same break across many books, and decide that pattern once.

`day` returns every task of one business date the caller may see — each with
the facts it is grouped by (`case.summarize_by`: key fields, or facts the
reference data holds about them, as in the subject) and its proposals still
open — so the console can group and filter without asking again.

`decide` applies one decision to many proposals across tasks. Nothing is
skipped: each task goes through the same `bulk_decide` a task's own "Approve
all" uses, so permissions, maker-checker, review.bulk_exclude, required
comments, open questions and checklists are checked per proposal, and what is
refused is reported with its reason.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select

from agent_one_finance import capabilities, deadlines, knowledge, review
from agent_one_finance import groups as team_groups
from agent_one_finance.cases import _settle, bulk_decide, may_see_case, scope_clause, visible_cases
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Case, CaseItem, Decision, ProposalGroup

MAX_DATES = 30
MAX_DECISIONS = 5000


class SummaryError(ValueError):
    pass


def date_field(m: Manifest) -> str | None:
    """The key field that dates a task: the one its deadline counts from, else the
    reference data's as-of field, else a key field named like a date."""
    key = m.case.key
    if m.case.due and m.case.due.from_ in key:
        return m.case.due.from_
    if m.knowledge.as_of in key:
        return m.knowledge.as_of
    return next((k for k in ("cob", "date", "business_date", "period") if k in key), None)


def _label(field: str, key: list[str]) -> str:
    k = next((k for k in key if field.startswith(f"{k}_")), None)
    return (field[len(k) + 1:] if k else field).replace("_", " ").capitalize()


async def _targets(capability_id: str, base: Manifest) -> list[tuple[str | None, Manifest]]:
    """(group, manifest) for each way the agent runs: its groups, or itself."""
    groups = await team_groups.active_groups(capability_id)
    return [(cfg.group, m) for _, cfg, m in groups] or [(None, base)]


def _on(group: str | None, field: str, value: str):
    return and_(Case.team_group == group if group else Case.team_group.is_(None),
                Case.case_key[field].astext == value)


async def _facts(m: Manifest, keys: list[dict], fields: list[str], date: str) -> list[dict]:
    """Each key's value of every summary field: the key's own, or the reference
    data's fact about it (as of the date), or None."""
    out = [{f: k.get(f) for f in fields if f in m.case.key} for k in keys]
    by_key: dict[str, list[str]] = defaultdict(list)
    for f in fields:
        if f in m.case.key:
            continue
        k = next((k for k in m.case.key if f.startswith(f"{k}_")), None)
        if k:
            by_key[k].append(f)
    if not by_key or not m.knowledge.reference:
        return out
    for k, wanted in by_key.items():
        nodes = await knowledge.walk(m.knowledge.reference, {f"{k}:{key.get(k)}" for key in keys}, [], as_of=date)
        for row, key in zip(out, keys):
            node = nodes.get(f"{k}:{key.get(k)}")
            for f in wanted:
                row[f] = (node.attrs if node else {}).get(f[len(k) + 1:])
    return out


def _may_decide(caller: Caller, absent: list[Caller], m: Manifest, case: Case) -> bool:
    if caller.has_any_role(m.review.roles) and may_see_case(caller, m, case.case_key):
        return True
    return m.review.allow_delegation and any(
        a.has_any_role(m.review.roles) and may_see_case(a, m, case.case_key) for a in absent)


async def day(capability_id: str, caller: Caller, date: str | None = None) -> dict:
    _, base = await capabilities.active(capability_id)
    if not await team_groups.visible(caller, capability_id, base):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}")
    targets = [(g, m, date_field(m)) for g, m in await _targets(capability_id, base) if capabilities.can_see(caller, m)]
    dated = [(g, m, f) for g, m, f in targets if f]
    active = {g: m for g, m, _ in targets}
    keys = [k for _, m, _ in targets for k in m.case.key]
    names = {cfg.group: cfg.name for _, cfg, _ in await team_groups.active_groups(capability_id)}

    async with get_session() as s:
        dates: set[str] = set()
        for g, _, f in dated:
            q = select(Case.case_key[f].astext).distinct().where(
                Case.capability_id == capability_id, Case.shadow_of.is_(None), scope_clause(caller),
                Case.team_group == g if g else Case.team_group.is_(None))
            dates |= {d for d in (await s.execute(q)).scalars() if d}
    dates_sorted = sorted(dates, reverse=True)[:MAX_DATES]
    date = date or (dates_sorted[0] if dates_sorted else None)
    visible = await visible_cases(caller, capability_id=capability_id,
                                  where=or_(*[_on(g, f, date) for g, _, f in dated])) if date and dated else []

    # Grouped by what the day's tasks are summarised by: the busiest group's facts first.
    present = Counter(c.team_group for c, _ in visible)
    fields: list[str] = []
    for g in [g for g, _ in present.most_common()] or list(active):
        m = active.get(g) or next(m for c, m in visible if c.team_group == g)
        fields += [f for f in m.case.summarize_by if f not in fields]
    dims = [{"field": f, "label": _label(f, keys)} for f in fields]
    if len(present) > 1:
        dims.append({"field": "team_group", "label": "Group"})
    out = {"capability_id": capability_id, "capability_name": base.name, "case_label": base.case.label,
           "dates": dates_sorted, "date": date, "dimensions": dims,
           "groups": [{"group": g, "name": names.get(g, g), "case_label": m.case.label,
                       "checklist": [{"id": q.id, "label": q.label, "required": q.required} for q in m.review.checklist]}
                      for g, m, _ in targets if g],
           "tasks": [], "totals": {}}
    if not visible:
        return out

    ids = [c.case_id for c, _ in visible]
    async with get_session() as s:
        groups = defaultdict(list)
        for g in (await s.execute(select(ProposalGroup).where(ProposalGroup.case_id.in_(ids)))).scalars():
            groups[g.case_id].append(g)
        decisions = defaultdict(list)
        for d in (await s.execute(select(Decision).where(Decision.case_id.in_(list(groups) or [""])))).scalars():
            decisions[d.case_id].append(d)
        items = defaultdict(dict)
        for it in (await s.execute(select(CaseItem).where(CaseItem.case_id.in_(list(groups) or [""])))).scalars():
            items[it.case_id][it.item_id] = it.payload
    absent = await review.covering_for(caller)
    now = datetime.now(timezone.utc)

    by_group: dict[str | None, list[tuple[Case, Manifest]]] = defaultdict(list)
    for c, m in visible:
        by_group[c.team_group].append((c, m))
    rows = []
    for g, pairs in by_group.items():
        view = active.get(g) or pairs[0][1]       # the group's current settings say how to summarise
        facts = await _facts(view, [c.case_key for c, _ in pairs], fields, date)
        for (c, m), fact in zip(pairs, facts):
            fact["team_group"] = names.get(c.team_group, c.team_group)
            gs = groups.get(c.case_id, [])
            its = items.get(c.case_id, {})
            ds = decisions.get(c.case_id, [])
            amount = m.items.amount_field
            can = c.status == "awaiting_review" and _may_decide(caller, absent, m, c)
            open_ = []
            settled = 0
            for grp in gs:
                if _settle(m, grp, ds, its) is not None:
                    settled += 1
                    continue
                f = grp.finding or {}
                mine = any(d.group_id == grp.group_id and d.decided_by == caller.user_id for d in ds)
                blockers = review.bulk_blockers(m, f)
                total = round(sum(abs(float(its.get(i, {}).get(amount) or 0)) for i in grp.item_ids), 2) if amount else None
                open_.append({"group_id": grp.group_id, "label": grp.label, "verdict": f.get("verdict"),
                              "status": f.get("status", "pending"), "items": len(grp.item_ids), "amount": total,
                              "flags": review.flags(f), "blockers": blockers,
                              "ready": can and not mine and not blockers and f.get("status") in ("proposed", "escalated"),
                              "needs_comment": f.get("status") == "escalated" and "escalated" in m.review.require_comment})
            draft = c.draft or {}
            rows.append({
                "case_id": c.case_id, "subject": c.subject, "team_group": c.team_group, "status": c.status,
                "outcome": c.outcome, "facts": [fact.get(d["field"]) for d in dims],
                "items": sum(len(x.item_ids) for x in gs), "groups": len(gs), "settled": settled,
                "exposure": draft.get("exposure"), "unit": draft.get("unit") or m.items.amount_unit,
                "due_at": c.due_at,
                "due_state": deadlines.state(c.due_at, c.status, now, m.case.due.warn_hours if m.case.due else 2),
                "can_decide": can, "open": open_,
            })
    out["tasks"] = rows
    out["totals"] = dict(Counter(r["status"] for r in rows))
    return out


async def decide(capability_id: str, targets: list[dict], action: str, comment: str | None,
                 idempotency_key: str, caller: Caller, review_seconds: int | None = None,
                 checklist: list[dict] | None = None) -> dict:
    """One decision on many proposals across tasks: `targets` = [{case_id, group_ids}]."""
    if action not in ("approve", "reject"):
        raise SummaryError("action must be approve or reject")
    count = sum(len(t.get("group_ids") or []) for t in targets)
    if not count:
        raise SummaryError("choose the proposals to decide")
    if count > MAX_DECISIONS:
        raise SummaryError(f"at most {MAX_DECISIONS} proposals at once; narrow the selection")
    ids = [t["case_id"] for t in targets]
    async with get_session() as s:
        ours = set((await s.execute(select(Case.case_id).where(
            Case.case_id.in_(ids), Case.capability_id == capability_id))).scalars())
    share = round(review_seconds / count) if review_seconds is not None else None
    decided, refused = 0, []
    for t in targets:
        gids = list(dict.fromkeys(t.get("group_ids") or []))
        if t["case_id"] not in ours:
            refused += [{"case_id": t["case_id"], "group_id": g, "reason": "not a task of this agent"} for g in gids]
            continue
        try:
            r = await bulk_decide(t["case_id"], gids, action, comment, f"{idempotency_key}:{t['case_id']}", caller,
                                  review_seconds=share * len(gids) if share is not None else None, checklist=checklist)
        except (LookupError, PermissionError, ValueError) as e:
            refused += [{"case_id": t["case_id"], "group_id": g, "reason": str(e)} for g in gids]
            continue
        decided += len(r["decided"])
        refused += [{"case_id": t["case_id"], **x} for x in r["refused"]]
    reasons = Counter(x["reason"] for x in refused)
    return {"decided": decided, "refused": refused[:200], "refused_count": len(refused),
            "reasons": [{"reason": k, "count": v} for k, v in reasons.most_common()]}
