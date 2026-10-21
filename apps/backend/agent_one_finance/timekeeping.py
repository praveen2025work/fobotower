"""Time-driven work the scheduler does every minute (with deadlines and
question chasing):

  waits   a task waiting at an `await` step past its timeout continues with
          {timed_out: true} — the step then escalates or carries on, as configured
  clocks  a `clock` step's clocks: the reviewers are warned before a clock
          runs out and told when it has; each notice once per clock
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from agent_one_finance.db import get_session
from agent_one_finance.models import Task

TERMINAL = ("completed", "failed", "stopped", "escalated")


async def check_waits(now: datetime | None = None) -> list[tuple[str, str]]:
    from agent_one_finance import runner
    now = now or datetime.now(timezone.utc)
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(Task.status.like("waiting_%"),
                                                   Task.waiting_since.is_not(None)))).scalars().all()
    done = []
    for task in rows:
        step = task.status[len("waiting_"):]
        m = await runner.pinned(task)
        cfg = m.step_config(step) if step in m.steps else None
        hours = getattr(cfg, "timeout_hours", None)
        if hours and now >= task.waiting_since + timedelta(hours=hours):
            await runner.deliver(task.task_id, step, {"timed_out": True, "at": now.isoformat()})
            done.append((task.task_id, "timed_out"))
    return done


async def check_clocks(now: datetime | None = None) -> list[tuple[str, str, str]]:
    from agent_one_finance import notify, runner
    now = now or datetime.now(timezone.utc)
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(Task.clock_state.is_not(None),
                                                   Task.status.not_in(TERMINAL)))).scalars().all()
        sent = []
        for task in rows:
            state = {k: dict(v) for k, v in (task.clock_state or {}).items()}
            m = await runner.pinned(task)
            for cid, c in state.items():
                due = datetime.fromisoformat(c["due_at"].replace("Z", "+00:00"))
                due = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
                kind = None
                if now >= due and not c.get("breached"):
                    c["breached"], kind = True, "clock_breached"
                elif now >= due - timedelta(hours=c.get("warn_before_hours", 4)) and not c.get("warned"):
                    c["warned"], kind = True, "clock_due_soon"
                if kind:
                    await notify.send(agent_id=task.agent_id, task_id=task.task_id, kind=kind,
                                      title=(f"{c['label']} runs out {due:%d %b %H:%M}" if kind == "clock_due_soon"
                                             else f"{c['label']} has run out") + f": {task.subject}",
                                      roles=list(m.review.roles), users=[task.opened_by])
                    sent.append((task.task_id, cid, kind))
                state[cid] = c
            task.clock_state = state
        await s.commit()
    return sent
