"""Follow-through: a decision is checked in the next run of the same series.

An agent names its series (the task-key fields that stay the same run to
run, e.g. book) and the field that advances (e.g. cob), and which approved
verdicts to follow. When the next run loads its items:

  - an item that was decided last time and is *still there* carries what was
    decided: `carried_verdict`, `carried_from` (the earlier task's subject) and
    `carried_runs` (how many runs it has been carried) — so the playbook or
    rules can act on it (a MONITOR that did not clear, an adjustment after which
    the break persists: "BO + adjustments ≠ FO, the investigation stays open");
  - an item that is *gone* has cleared: the earlier task records it.

Each followed item gets one row in aof_follow_through, updated by the latest
run that checked it, so the earlier task shows what cleared and what did not.
Generic: FOBO follows POST / CORRECT_AND_REPOST / MONITOR; a cash rec follows
write-offs; any agent with a recurring series can follow its decisions.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select

from agent_one_finance.db import get_session
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Task, TaskItem, Decision, FollowThrough, ProposalGroup


def _series(m: Manifest, key: dict) -> dict:
    return {f: key.get(f) for f in m.follow_through.series}


async def _previous_tasks(state: dict, m: Manifest) -> list[Task]:
    """Every task (first run, attempts, follow-ups) of the latest earlier key in
    the series — e.g. yesterday's COB for this book."""
    ft = m.follow_through
    key = state["task_key"]
    async with get_session() as s:
        this = await s.get(Task, state["task_id"])
        q = select(Task).where(Task.agent_id == state["agent_id"],
                               Task.task_id != state["task_id"], Task.shadow_of.is_(None))
        q = q.where(Task.team_group == this.team_group) if this.team_group else q.where(Task.team_group.is_(None))
        for f in ft.series:
            q = q.where(Task.task_key[f].astext == str(key.get(f)))
        rows = (await s.execute(q)).scalars().all()
    earlier = [c for c in rows if str(c.task_key.get(ft.order_by, "")) < str(key.get(ft.order_by, ""))]
    if not earlier:
        return []
    last = max(str(c.task_key.get(ft.order_by, "")) for c in earlier)
    return [c for c in earlier if str(c.task_key.get(ft.order_by, "")) == last]


async def _followed(tasks: list[Task], m: Manifest) -> dict[str, dict]:
    """item_id → what was decided on it: approved groups whose verdict is followed."""
    if not tasks:
        return {}
    ids = [c.task_id for c in tasks]
    subject = {c.task_id: c.subject for c in tasks}
    async with get_session() as s:
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.task_id.in_(ids)))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.task_id.in_(ids))
                                     .order_by(Decision.decided_at))).scalars().all()
        items = {(i.task_id, i.item_id): i.payload for i in (await s.execute(
            select(TaskItem).where(TaskItem.task_id.in_(ids)))).scalars()}
    latest = {(d.task_id, d.group_id): d for d in decisions}
    out = {}
    for g in groups:
        d = latest.get((g.task_id, g.group_id))
        verdict = (g.finding or {}).get("verdict") or (g.finding or {}).get("status")
        if d is None or d.action != "approve":
            continue
        if m.follow_through.verdicts and verdict not in m.follow_through.verdicts:
            continue
        for item_id in g.item_ids:
            prior = items.get((g.task_id, item_id), {})
            out[item_id] = {"verdict": verdict, "task_id": g.task_id, "subject": subject[g.task_id],
                            "runs": int(prior.get("carried_runs") or 0), "decided_by": d.decided_by}
    return out


async def carry(state: dict, m: Manifest, items: list[dict]) -> list[dict]:
    """Mark what is carried from the last run, and record what cleared."""
    if m.follow_through is None or state.get("follow_up_of"):
        return items
    followed = await _followed(await _previous_tasks(state, m), m)
    present = {it["item_id"] for it in items}
    out = []
    for it in items:
        f = followed.get(it["item_id"])
        out.append({**it, "carried_verdict": f["verdict"] if f else None,
                    "carried_from": f["subject"] if f else None,
                    "carried_runs": f["runs"] + 1 if f else 0})
    now = datetime.now(timezone.utc)
    async with get_session() as s:
        for item_id, f in followed.items():
            await s.execute(delete(FollowThrough).where(
                FollowThrough.task_id == f["task_id"], FollowThrough.item_id == item_id))
            s.add(FollowThrough(task_id=f["task_id"], item_id=item_id, verdict=f["verdict"],
                                status="still_open" if item_id in present else "cleared",
                                checked_in=state["task_id"], checked_at=now))
        await s.commit()
    return out


async def for_task(task_id: str) -> dict | None:
    """What became of this task's followed decisions in the next run."""
    async with get_session() as s:
        rows = (await s.execute(select(FollowThrough).where(FollowThrough.task_id == task_id)
                                .order_by(FollowThrough.item_id))).scalars().all()
    if not rows:
        return None
    return {"cleared": sum(r.status == "cleared" for r in rows),
            "still_open": sum(r.status == "still_open" for r in rows),
            "items": [{"item_id": r.item_id, "verdict": r.verdict, "status": r.status,
                       "checked_in": r.checked_in, "checked_at": r.checked_at} for r in rows]}
