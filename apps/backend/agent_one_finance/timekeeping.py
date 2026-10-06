"""Time-driven work the scheduler does every minute (with deadlines and
question chasing):

  waits   a case waiting at an `await` step past its timeout continues with
          {timed_out: true} — the step then escalates or carries on, as configured
  clocks  a `clock` step's clocks: the reviewers are warned before a clock
          runs out and told when it has; each notice once per clock
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from agent_one_finance.db import get_session
from agent_one_finance.models import Case

TERMINAL = ("completed", "failed", "stopped", "escalated")


async def check_waits(now: datetime | None = None) -> list[tuple[str, str]]:
    from agent_one_finance import runner
    now = now or datetime.now(timezone.utc)
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(Case.status.like("waiting_%"),
                                                   Case.waiting_since.is_not(None)))).scalars().all()
    done = []
    for case in rows:
        step = case.status[len("waiting_"):]
        m = await runner.pinned(case)
        cfg = m.step_config(step) if step in m.steps else None
        hours = getattr(cfg, "timeout_hours", None)
        if hours and now >= case.waiting_since + timedelta(hours=hours):
            await runner.deliver(case.case_id, step, {"timed_out": True, "at": now.isoformat()})
            done.append((case.case_id, "timed_out"))
    return done


async def check_clocks(now: datetime | None = None) -> list[tuple[str, str, str]]:
    from agent_one_finance import notify, runner
    now = now or datetime.now(timezone.utc)
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(Case.clock_state.is_not(None),
                                                   Case.status.not_in(TERMINAL)))).scalars().all()
        sent = []
        for case in rows:
            state = {k: dict(v) for k, v in (case.clock_state or {}).items()}
            m = await runner.pinned(case)
            for cid, c in state.items():
                due = datetime.fromisoformat(c["due_at"].replace("Z", "+00:00"))
                due = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
                kind = None
                if now >= due and not c.get("breached"):
                    c["breached"], kind = True, "clock_breached"
                elif now >= due - timedelta(hours=c.get("warn_before_hours", 4)) and not c.get("warned"):
                    c["warned"], kind = True, "clock_due_soon"
                if kind:
                    await notify.send(capability_id=case.capability_id, case_id=case.case_id, kind=kind,
                                      title=(f"{c['label']} runs out {due:%d %b %H:%M}" if kind == "clock_due_soon"
                                             else f"{c['label']} has run out") + f": {case.subject}",
                                      roles=list(m.review.roles), users=[case.opened_by])
                    sent.append((case.case_id, cid, kind))
                state[cid] = c
            case.clock_state = state
        await s.commit()
    return sent
