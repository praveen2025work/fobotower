"""Retention: finished tasks are removed when their agent's
`retention.days` have passed, unless a legal hold is on the task.

Removing a task removes everything recorded for it — items, groups,
decisions, chat, tool calls, the reports it published, its LangGraph
checkpoints and what it taught the knowledge graph — and leaves one
aof_retention_event row saying that it existed and when it went.

    python -m agent_one_finance.retention              # purge what is due
    python -m agent_one_finance.retention --dry-run    # list what would go
"""

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text

from agent_one_finance import agents, knowledge
from agent_one_finance.db import engine, get_session
from agent_one_finance.models import Task, Document, RetentionEvent, ToolCall

FINISHED = ("completed", "failed", "escalated", "shadow")


async def due(now: datetime | None = None) -> list[tuple[Task, int]]:
    """(task, retention days) for every finished task past its retention."""
    now = now or datetime.now(timezone.utc)
    out = []
    for _, m in await agents.all_active():
        if m.retention is None:
            continue
        cutoff = now - timedelta(days=m.retention.days)
        async with get_session() as s:
            rows = (await s.execute(select(Task).where(
                Task.agent_id == m.id, Task.status.in_(FINISHED),
                Task.legal_hold.is_(False), Task.opened_at < cutoff))).scalars().all()
        out += [(c, m.retention.days) for c in rows]
    return out


async def purge(now: datetime | None = None, by: str = "system:retention",
                dry_run: bool = False) -> list[str]:
    tasks = await due(now)
    if dry_run:
        return [c.task_id for c, _ in tasks]
    for task, days in tasks:
        async with get_session() as s:
            calls = (await s.execute(select(ToolCall).where(ToolCall.task_id == task.task_id))).scalars().all()
            for c in calls:
                r = c.result if isinstance(c.result, dict) else {}
                if c.requested_by == "publish" and r.get("document") and r.get("scope"):
                    await s.execute(delete(Document).where(Document.scope == r["scope"],
                                                           Document.name == r["document"]))
            await s.execute(delete(ToolCall).where(ToolCall.task_id == task.task_id))
            await s.execute(delete(Task).where(Task.task_id == task.task_id))   # cascades
            s.add(RetentionEvent(event_id=uuid.uuid4().hex, task_id=task.task_id,
                                 agent_id=task.agent_id, subject=task.subject,
                                 opened_at=task.opened_at, retention_days=days, purged_by=by))
            await s.commit()
        await knowledge.forget_task(task.agent_id, task.task_id)
        async with engine.begin() as conn:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                await conn.execute(text(f"DELETE FROM {table} WHERE thread_id = :t"),
                                   {"t": f"aof:{task.task_id}"})
    return [c.task_id for c, _ in tasks]


async def set_legal_hold(task_id: str, hold: bool, reason: str | None, caller) -> dict:
    """Agent owners put a task on (or take it off) legal hold. A held
    task is never removed by retention."""
    from agent_one_finance.tasks import TaskError, _pinned

    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        _, current = await agents.active(task.agent_id)
        if not (agents.is_owner(caller, m) or agents.is_owner(caller, current)):
            raise PermissionError(f"{caller.user_id} does not own {task.agent_id}")
        if hold and not (reason or "").strip():
            raise TaskError("a legal hold needs a reason")
        task.legal_hold = hold
        task.legal_hold_reason = (reason or "").strip() or None if hold else None
        await s.commit()
        return {"legal_hold": task.legal_hold, "legal_hold_reason": task.legal_hold_reason}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    ids = asyncio.run(purge(dry_run=a.dry_run))
    print(("would remove" if a.dry_run else "removed"), len(ids), "task(s)")
    for i in ids:
        print(" ", i)


if __name__ == "__main__":
    main()
