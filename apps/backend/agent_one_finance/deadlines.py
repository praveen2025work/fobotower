"""When a task is due, and the reminders when it is near or missed.

Configured by `task.due` in the manifest (agent or group):

    task:
      due:
        from: cob            # "opened" (default) or a task-key date field: YYYY-MM-DD,
                             # or YYYY-MM (the month's last day)
        business_days: 1     # Monday to Friday
        hours: 0
        at: "11:00"          # time of day (AOF_SCHEDULE_TZ); optional
        warn_hours: 2        # "due soon" this long before

A task is done when it leaves review and release (completed, escalated,
failed). The scheduler's leader checks every minute: "due soon" goes to the
reviewers, "missed" to the reviewers and the owners — each once per task.
"""

import calendar
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from agent_one_finance import notify
from agent_one_finance.db import get_session
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Task
from agent_one_finance.scheduler import tz

log = logging.getLogger("agent_one_finance.deadlines")

OPEN_STATUSES = ("running", "awaiting_review", "awaiting_publish")
GATE_PREFIX = "paused_before_"     # waiting at a tollgate: also open


def is_open(status: str) -> bool:
    return status in OPEN_STATUSES or status.startswith(GATE_PREFIX)


def _base(spec_from: str, task_key: dict, opened_at: datetime) -> datetime:
    if spec_from == "opened":
        return opened_at.astimezone(tz())
    raw = str(task_key.get(spec_from, ""))
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        y, mo = (int(x) for x in raw.split("-")[:2])
        d = date(y, mo, calendar.monthrange(y, mo)[1])
    return datetime.combine(d, time(0, 0), tzinfo=tz())


def _add_business_days(at: datetime, n: int) -> datetime:
    while n > 0:
        at += timedelta(days=1)
        if at.weekday() < 5:
            n -= 1
    return at


def due_at(m: Manifest, task_key: dict, opened_at: datetime) -> datetime | None:
    spec = m.task.due
    if spec is None:
        return None
    try:
        at = _base(spec.from_, task_key, opened_at)
    except (ValueError, TypeError):
        log.warning("task.due: cannot read %r from %s", spec.from_, task_key)
        return None
    at = _add_business_days(at, spec.business_days) + timedelta(hours=spec.hours)
    if spec.at:
        hh, mm = (int(x) for x in spec.at.split(":"))
        at = at.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return at


def state(due: datetime | None, status: str, now: datetime, warn_hours: float = 2) -> str | None:
    """on_time | due_soon | overdue — for open tasks with a due date; None otherwise."""
    if due is None or not is_open(status):
        return None
    if now >= due:
        return "overdue"
    return "due_soon" if now >= due - timedelta(hours=warn_hours) else "on_time"


async def check(now: datetime | None = None) -> list[tuple[str, str]]:
    """Send each due-soon and missed reminder once. Returns (task_id, kind) sent."""
    from agent_one_finance.runner import pinned

    now = now or datetime.now(tz())
    async with get_session() as s:
        tasks = (await s.execute(select(Task).where(
            Task.due_at.is_not(None), Task.status.in_(OPEN_STATUSES) | Task.status.startswith(GATE_PREFIX),
            Task.shadow_of.is_(None),
            (Task.due_notified.is_(None)) | (Task.due_notified == "soon")))).scalars().all()
    sent = []
    for c in tasks:
        m = await pinned(c)
        st = state(c.due_at, c.status, now, m.task.due.warn_hours if m.task.due else 2)
        kind = {"overdue": "missed", "due_soon": "soon"}.get(st or "")
        if kind is None or kind == c.due_notified:
            continue
        what = f"{m.task.label}: {c.subject}"
        when = c.due_at.astimezone(tz()).strftime("%d %b %H:%M")
        if kind == "soon":
            await notify.send(agent_id=c.agent_id, task_id=c.task_id, kind="due_soon",
                              title=f"{what} is due {when}", roles=list(m.review.roles))
        else:
            await notify.send(agent_id=c.agent_id, task_id=c.task_id, kind="overdue",
                              title=f"{what} missed its deadline ({when})",
                              roles=list(m.review.roles) + ([m.owners.role] if m.owners.role else []),
                              users=list(m.owners.people))
        async with get_session() as s:
            row = await s.get(Task, c.task_id)
            row.due_notified = kind
            await s.commit()
        sent.append((c.task_id, kind))
    return sent
