"""Task runs, off the request path.

Opening a task, completing its review and releasing its write-back each run
the task's LangGraph graph — with a model that can take minutes. The API
records what should happen, answers at once with the task "running", and the
run happens here. The LangGraph checkpoint is the durable record of progress:
a server that restarts finds every task left "running" and finishes it from
its last checkpoint (`recover`).

  AOF_RUN_MODE=background   (default) asyncio tasks in the API process
  AOF_RUN_MODE=inline       the run finishes before the call returns
                              (tests, scripts)

One run per task at a time across every API instance: the run holds a
Postgres advisory lock on the task id.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from agent_one_finance.config import settings
from agent_one_finance.db import engine, get_session
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Task, AgentVersion
from agent_one_finance.observability import current_trace_id, span
from agent_one_finance.workflow import build_graph, checkpointer

log = logging.getLogger("agent_one_finance.runner")

_tasks: set[asyncio.Task] = set()
_slots: tuple[asyncio.AbstractEventLoop, int, asyncio.Semaphore] | None = None


def _slot() -> asyncio.Semaphore:
    """At most settings().max_runs background runs at once, per event loop."""
    global _slots
    loop, n = asyncio.get_running_loop(), max(1, settings().max_runs)
    if _slots is None or _slots[0] is not loop or _slots[1] != n:
        _slots = (loop, n, asyncio.Semaphore(n))
    return _slots[2]


async def _in_turn(work):
    async with _slot():
        await work


# Tasks opened on the same agent and group versions share one snapshot: a day of
# 1,000+ tasks is read without checking the same manifest again for each.
_pinned_cache: dict[tuple, tuple[dict, Manifest]] = {}


async def pinned(task: Task) -> Manifest:
    """The exact manifest the task runs on: its snapshot (agent + group),
    or for older tasks the agent version it opened with."""
    if task.manifest:
        key = (task.agent_id, task.manifest_version, task.team_group, task.team_group_version)
        hit = _pinned_cache.get(key)
        if hit is not None and hit[0] == task.manifest:     # the very same snapshot
            return hit[1]
        m = Manifest.model_validate(task.manifest)
        if len(_pinned_cache) >= 64:
            _pinned_cache.pop(next(iter(_pinned_cache)))
        _pinned_cache[key] = (task.manifest, m)
        return m
    async with get_session() as s:
        row = await s.get(AgentVersion, (task.agent_id, task.manifest_version))
    return Manifest.model_validate(row.manifest)


def initial_state(task: Task, m: Manifest) -> dict:
    return {"task_id": task.task_id, "agent_id": task.agent_id,
            "manifest_version": task.manifest_version, "manifest": m.model_dump(by_alias=True),
            "task_key": task.task_key, "caller": task.run_as,
            **({"follow_up_of": task.follow_up_of} if task.follow_up_of else {})}


def _config(task_id: str) -> dict:
    return {"configurable": {"thread_id": f"aof:{task_id}"}}


@asynccontextmanager
async def task_lock(task_id: str):
    """Held for a whole run; a second run of the same task waits for it."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(hashtextextended(:k, 0))"), {"k": task_id})
        try:
            yield
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"),
                               {"k": task_id})
            await conn.commit()


async def _status_after_run(app, task_id: str, m: Manifest | None = None) -> str:
    snapshot = await app.aget_state(_config(task_id))
    release = m.release_step() if m else "publish"
    waits = m.waits() if m else []
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if "review" in snapshot.next:
            task.status = "awaiting_review"
            if task.review_ready_at is None:           # the start of measured review time
                task.review_ready_at = func.now()
        elif release and release in snapshot.next:
            task.status = "awaiting_publish"
        elif snapshot.next and snapshot.next[0] in waits:
            if not task.status.startswith("waiting_"):
                task.waiting_since = func.now()
            task.status = f"waiting_{snapshot.next[0]}"
        elif snapshot.next:
            task.status = f"paused_before_{snapshot.next[0]}"
        elif task.status == "running":     # ended without a step setting the outcome
            task.status = "completed"
        await s.commit()
        return task.status


async def _nothing_new(task_id: str) -> str:
    """A follow-up that found no late items: there is nothing to work."""
    async with get_session() as s:
        task = await s.get(Task, task_id)
        task.status, task.outcome = "completed", "no_new_items"
        await s.commit()
    return "completed"


async def fail(task_id: str, e: BaseException) -> None:
    async with get_session() as s:
        task = await s.get(Task, task_id)
        task.status, task.error = "failed", f"{type(e).__name__}: {e}"
        await s.commit()


# What each pause waits for; nothing else moves a run past it. Any other
# pause is a tollgate, crossed only when a person passes it.
_CROSSES = {"review": {"decisions"}, "publish": {"publish_approval"}}
_GATE = {"gates_passed", "gate_notes"}
TERMINAL = ("completed", "failed", "stopped", "escalated")


def _crosses(m: Manifest, step: str) -> set[str]:
    if step == m.release_step():
        return {"publish_approval"}
    if step in m.waits():
        return {"events"}
    return _CROSSES.get(step, _GATE)


async def children_done(task_id: str) -> dict | None:
    """The outcome of a task's child tasks, once every one has finished; else None."""
    async with get_session() as s:
        kids = (await s.execute(select(Task).where(Task.parent_task_id == task_id))).scalars().all()
    if not kids or any(k.status not in TERMINAL for k in kids):
        return None
    return {k.task_id: {"status": k.status, "outcome": k.outcome, "subject": k.subject} for k in kids}

_SPANS = {"open": "task.run", "resume": "review.resume", "publish": "publish.release",
          "recover": "task.recover"}


async def run_task(task_id: str, kind: str = "open", update: dict | None = None) -> str:
    """Run (or continue) a task's graph to its next pause or its end.

    `update` is merged into the checkpointed state first (the decisions, or
    the write-back release). With no checkpoint yet, the run starts from the
    task row."""
    async with task_lock(task_id):
        async with get_session() as s:
            task = await s.get(Task, task_id)
        m = await pinned(task)
        config = _config(task_id)
        with span(_SPANS.get(kind, "task.run"), root=True, task_id=task_id,
                  agent_id=task.agent_id, manifest_version=task.manifest_version,
                  user=(task.run_as or {}).get("user_id")):
            trace_id = current_trace_id()
            try:
                async with checkpointer() as cp:
                    app = build_graph(m.steps, m.pause_before, cp, m.step_types())
                    snap = await app.aget_state(config)
                    started = snap.created_at is not None
                    paused_at = snap.next[0] if snap.next and snap.next[0] in m.pauses() else None
                    if paused_at and (not update or not set(update) <= _crosses(m, paused_at)):
                        # A pause is crossed only with what it waits for — never by
                        # a bare resume (a recovery must not skip a person's sign-off).
                        return await _status_after_run(app, task_id, m)
                    if started and "task_id" not in (snap.values or {}):
                        # Checkpointed before tasks and agents were renamed: the run
                        # continues with its identity and configuration from the task row.
                        await app.aupdate_state(config, {k: v for k, v in initial_state(task, m).items()
                                                         if k != "follow_up_of"})
                    if update:
                        await app.aupdate_state(config, update)
                    await app.ainvoke(None if started else initial_state(task, m), config)
                    after = await app.aget_state(config)
                    if after.next and after.next[0] == "review" and not (after.values or {}).get("groups"):
                        # Nothing in scope: no one has anything to decide, so the
                        # review pause is crossed with no decisions and the run records.
                        await app.aupdate_state(config, {"decisions": []})
                        await app.ainvoke(None, config)
                    after = await app.aget_state(config)
                    while after.next and after.next[0] in m.waits():
                        # Waiting for child tasks that have all finished already:
                        # cross at once with their outcomes.
                        cfg = m.step_config(after.next[0])
                        done = await children_done(task_id) if getattr(cfg, "event", "") == "children" else None
                        if done is None:
                            break
                        events = dict((after.values or {}).get("events") or {})
                        events[after.next[0]] = {"children": done}
                        await app.aupdate_state(config, {"events": events})
                        await app.ainvoke(None, config)
                        after = await app.aget_state(config)
                    release = m.release_step()
                    if after.next and after.next[0] == release and not any(
                            d.get("action") == "approve" for d in (after.values or {}).get("decisions", [])):
                        # Nothing approved means nothing to write: no one is asked to
                        # release an empty write-back; publish runs and writes nothing.
                        await app.aupdate_state(config, {"publish_approval": {
                            "approved_by": None, "approved_at": now_iso(), "nothing_to_write": True}})
                        await app.ainvoke(None, config)
                    status = await _status_after_run(app, task_id, m)
                    values = (await app.aget_state(config)).values or {}
                    if values.get("follow_up_of") and not values.get("items"):
                        status = await _nothing_new(task_id)
            except Exception as e:
                log.exception("task %s: run failed", task_id)
                await fail(task_id, e)
                status = "failed"
        if status == "failed":
            await _announce(task_id)
            await _wake_parent(task_id)
            return status
        if trace_id and kind == "open":
            async with get_session() as s:
                row = await s.get(Task, task_id)
                row.trace_id = row.trace_id or trace_id
                await s.commit()
    await _announce(task_id)
    await _wake_parent(task_id)
    return status


async def _wake_parent(task_id: str) -> None:
    """A child task finished: when all its siblings have too and the parent is
    waiting for them, the parent continues with their outcomes."""
    async with get_session() as s:
        task = await s.get(Task, task_id)
        parent = await s.get(Task, task.parent_task_id) if task and task.parent_task_id else None
    if parent is None or task.status not in TERMINAL or not parent.status.startswith("waiting_"):
        return
    done = await children_done(parent.task_id)
    if done is None:
        return
    step = parent.status[len("waiting_"):]
    m = await pinned(parent)
    if getattr(m.step_config(step), "event", "") != "children":
        return
    await deliver(parent.task_id, step, {"children": done})


async def deliver(task_id: str, step: str, payload: dict) -> None:
    """An event for a task waiting at an `await` step: it continues with it."""
    async with task_lock(task_id):
        async with checkpointer() as cp:
            async with get_session() as s:
                task = await s.get(Task, task_id)
            m = await pinned(task)
            app = build_graph(m.steps, m.pause_before, cp, m.step_types())
            values = (await app.aget_state(_config(task_id))).values or {}
        events = dict(values.get("events") or {})
        events[step] = payload
        async with get_session() as s:
            row = await s.get(Task, task_id)
            row.status, row.waiting_since = "running", None
            await s.commit()
    await submit(task_id, "event", {"events": events})


async def _announce(task_id: str) -> None:
    from agent_one_finance import notify
    try:
        await notify.task_changed(task_id)
    except Exception:          # telling people must never break a run
        log.exception("task %s: notification failed", task_id)


async def submit(task_id: str, kind: str = "open", update: dict | None = None) -> None:
    """Run the task now (inline) or in the background. The caller has already
    set the task's status to "running"."""
    if settings().run_mode == "inline":
        await run_task(task_id, kind, update)
        return
    task = asyncio.create_task(_in_turn(run_task(task_id, kind, update)), name=f"aof:{task_id}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def run_job(task_id: str, job, label: str) -> None:
    """Some other work on a paused task (e.g. re-investigating one group),
    under the same lock as a run; a failure fails the task visibly."""
    async with task_lock(task_id):
        with span(label, root=True, task_id=task_id):
            try:
                await job()
            except Exception as e:
                log.exception("task %s: %s failed", task_id, label)
                await fail(task_id, e)
    await _announce(task_id)


async def submit_job(task_id: str, job, label: str) -> None:
    if settings().run_mode == "inline":
        await run_job(task_id, job, label)
        return
    task = asyncio.create_task(_in_turn(run_job(task_id, job, label)), name=f"aof:{task_id}:{label}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for every background run (tests, graceful shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def recover() -> list[str]:
    """At startup: finish every task left running by a stopped server."""
    async with get_session() as s:
        ids = (await s.execute(select(Task.task_id).where(
            Task.status == "running", Task.shadow_of.is_(None)))).scalars().all()
    for task_id in ids:
        await submit(task_id, "recover")
    return list(ids)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
