"""Notifications: tell people when a task needs them or has moved on.

After every run (or job) the task's new state decides who hears about it:

  awaiting_review    the agent's reviewers           "needs your review"
  awaiting_publish   the write-back approvers             "needs your release"
  paused_before_X    the tollgate's roles                 "waits for you before X"
  completed          whoever opened it, and its deciders  "completed" / "published"
  failed             whoever opened it, and the owners    "failed: …"
  escalated          whoever opened it, and the reviewers "escalated"

Each is addressed to roles and people and shown in the console's bell only
to those who may also see the task. With AOF_NOTIFY_WEBHOOK_URL set, each
is also POSTed there — a Teams incoming webhook, or a Power Automate flow
that emails or posts it. A webhook failure is logged, never raised.
"""

import logging
import uuid

import httpx
from sqlalchemy import select

from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.models import Task, Decision, Notification, NotificationRead

log = logging.getLogger("agent_one_finance.notify")


async def _send_webhook(n: Notification, link: str, extra: dict | None = None) -> None:
    url = settings().notify_webhook_url
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={"title": n.title, "text": f"{n.title} — {n.body} {link}".strip(),
                                         "link": link, "kind": n.kind, "task_id": n.task_id,
                                         "agent_id": n.agent_id,
                                         "audience_roles": n.audience_roles,
                                         "audience_users": n.audience_users, **(extra or {})})
    except Exception:
        log.exception("notification webhook failed")


async def send(*, agent_id: str, kind: str, title: str, body: str = "", task_id: str | None = None,
               roles: list[str] | None = None, users: list[str] | None = None,
               extra: dict | None = None) -> str:
    """`extra` goes to the webhook only, e.g. a question's id and where a bot
    posts the answer, so a Teams or email flow can reply without the console."""
    n = Notification(notification_id=uuid.uuid4().hex, task_id=task_id, agent_id=agent_id,
                     kind=kind, title=title, body=body, audience_roles=sorted(set(roles or [])),
                     audience_users=sorted(set(users or [])))
    async with get_session() as s:
        s.add(n)
        await s.commit()
    await _send_webhook(n, f"{settings().console_url}/tasks/{task_id}" if task_id else settings().console_url, extra)
    return n.notification_id


async def task_changed(task_id: str) -> None:
    """Called after a run or job: announce the task's state, once per state."""
    from agent_one_finance.runner import pinned

    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None or task.shadow_of:        # trial runs tell nobody
            return
        last = (await s.execute(select(Notification.kind).where(Notification.task_id == task_id)
                                .order_by(Notification.created_at.desc()).limit(1))).scalar()
        deciders = sorted(set((await s.execute(select(Decision.decided_by).where(
            Decision.task_id == task_id))).scalars()))
    m = await pinned(task)
    what = f"{m.task.label}: {task.subject}"
    owners_role = [m.owners.role] if m.owners.role else []
    plan = {
        "awaiting_review": ("review_needed", f"{what} needs your review",
                            (task.draft or {}).get("headline", ""), m.review.roles, []),
        "awaiting_publish": ("release_needed", f"{what} needs a second person to release it",
                             f"Reviewed by {', '.join(deciders)}", m.release_roles(), []),
        "completed": ("published" if task.outcome == "published" else "completed",
                      f"{what} {'published' if task.outcome == 'published' else 'completed'}",
                      "", [], [task.opened_by, *deciders]),
        "failed": ("failed", f"{what} failed", task.error or "", owners_role, [task.opened_by, *m.owners.people]),
        "escalated": ("escalated", f"{what} was escalated", task.error or "",
                      m.review.roles, [task.opened_by]),
        "stopped": ("stopped", f"{what} was stopped at a tollgate", task.error or "",
                    owners_role, [task.opened_by]),
    }.get(task.status)
    if plan is None and task.status.startswith("paused_before_"):
        step = task.status[len("paused_before_"):]
        gate = m.gate(step)
        plan = ("gate_needed", f"{what} waits for you before `{step}`",
                gate.check or "Check the work so far, then continue or stop the run.", gate.roles, [])
    if plan is None or plan[0] == last:
        return
    kind, title, body, roles, users = plan
    await send(agent_id=task.agent_id, task_id=task_id, kind=kind, title=title,
               body=body[:500], roles=list(roles), users=users)


# A question goes to people who may not see the task (a trader, Operations):
# they see the question itself, as in Inbox → Questions for you.
QUESTION_KINDS = {"question", "question_reminder"}


def _addressed(n: Notification, caller: Caller) -> bool:
    return caller.user_id in (n.audience_users or []) or bool(set(n.audience_roles or []) & caller.roles)


async def for_caller(caller: Caller, limit: int = 50) -> dict:
    """The caller's newest notifications (only for tasks they may see)."""
    from agent_one_finance.tasks import may_see_task
    from agent_one_finance.runner import pinned

    async with get_session() as s:
        rows = (await s.execute(select(Notification).order_by(Notification.created_at.desc())
                                .limit(500))).scalars().all()
        read = set((await s.execute(select(NotificationRead.notification_id).where(
            NotificationRead.user_id == caller.user_id))).scalars())
        out = []
        for n in rows:
            if not _addressed(n, caller):
                continue
            if n.task_id and n.kind not in QUESTION_KINDS:
                task = await s.get(Task, n.task_id)
                if task is None or not may_see_task(caller, await pinned(task), task.task_key):
                    continue
            out.append({"notification_id": n.notification_id, "kind": n.kind, "title": n.title,
                        "body": n.body, "task_id": n.task_id, "agent_id": n.agent_id,
                        "created_at": n.created_at, "read": n.notification_id in read})
            if len(out) >= limit:
                break
    return {"unread": sum(1 for n in out if not n["read"]), "items": out}


async def mark_read(caller: Caller, ids: list[str] | None) -> int:
    mine = [n["notification_id"] for n in (await for_caller(caller, limit=500))["items"] if not n["read"]]
    targets = [i for i in mine if ids is None or i in ids]
    async with get_session() as s:
        for i in targets:
            await s.merge(NotificationRead(notification_id=i, user_id=caller.user_id))
        await s.commit()
    return len(targets)
