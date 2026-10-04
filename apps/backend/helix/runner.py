"""Case runs, off the request path.

Opening a case, completing its review and releasing its write-back each run
the case's LangGraph graph — with a model that can take minutes. The API
records what should happen, answers at once with the case "running", and the
run happens here. The LangGraph checkpoint is the durable record of progress:
a server that restarts finds every case left "running" and finishes it from
its last checkpoint (`recover`).

  HELIX_RUN_MODE=background   (default) asyncio tasks in the API process
  HELIX_RUN_MODE=inline       the run finishes before the call returns
                              (tests, scripts)

One run per case at a time across every API instance: the run holds a
Postgres advisory lock on the case id.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import select, text

from helix.config import settings
from helix.db import engine, get_session
from helix.manifest import Manifest
from helix.models import Case, CapabilityVersion
from helix.observability import current_trace_id, span
from helix.workflow import build_graph, checkpointer

log = logging.getLogger("helix.runner")

_tasks: set[asyncio.Task] = set()


async def pinned(case: Case) -> Manifest:
    """The exact manifest the case runs on: its snapshot (capability + group),
    or for older cases the capability version it opened with."""
    if case.manifest:
        return Manifest.model_validate(case.manifest)
    async with get_session() as s:
        row = await s.get(CapabilityVersion, (case.capability_id, case.manifest_version))
    return Manifest.model_validate(row.manifest)


def initial_state(case: Case, m: Manifest) -> dict:
    return {"case_id": case.case_id, "capability_id": case.capability_id,
            "manifest_version": case.manifest_version, "manifest": m.model_dump(by_alias=True),
            "case_key": case.case_key, "caller": case.run_as}


def _config(case_id: str) -> dict:
    return {"configurable": {"thread_id": f"helix:{case_id}"}}


@asynccontextmanager
async def case_lock(case_id: str):
    """Held for a whole run; a second run of the same case waits for it."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT pg_advisory_lock(hashtextextended(:k, 0))"), {"k": case_id})
        try:
            yield
        finally:
            await conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"),
                               {"k": case_id})
            await conn.commit()


async def _status_after_run(app, case_id: str) -> str:
    snapshot = await app.aget_state(_config(case_id))
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if "review" in snapshot.next:
            case.status = "awaiting_review"
        elif "publish" in snapshot.next:
            case.status = "awaiting_publish"
        elif snapshot.next:
            case.status = f"paused_before_{snapshot.next[0]}"
        elif case.status == "running":     # ended without a step setting the outcome
            case.status = "completed"
        await s.commit()
        return case.status


async def fail(case_id: str, e: BaseException) -> None:
    async with get_session() as s:
        case = await s.get(Case, case_id)
        case.status, case.error = "failed", f"{type(e).__name__}: {e}"
        await s.commit()


# What each pause waits for; nothing else moves a run past it.
_CROSSES = {"review": {"decisions"}, "publish": {"publish_approval"}}

_SPANS = {"open": "case.run", "resume": "review.resume", "publish": "publish.release",
          "recover": "case.recover"}


async def run_case(case_id: str, kind: str = "open", update: dict | None = None) -> str:
    """Run (or continue) a case's graph to its next pause or its end.

    `update` is merged into the checkpointed state first (the decisions, or
    the write-back release). With no checkpoint yet, the run starts from the
    case row."""
    async with case_lock(case_id):
        async with get_session() as s:
            case = await s.get(Case, case_id)
        m = await pinned(case)
        config = _config(case_id)
        with span(_SPANS.get(kind, "case.run"), root=True, case_id=case_id,
                  capability_id=case.capability_id, manifest_version=case.manifest_version,
                  user=(case.run_as or {}).get("user_id")):
            trace_id = current_trace_id()
            try:
                async with checkpointer() as cp:
                    app = build_graph(m.steps, m.pause_before, cp)
                    snap = await app.aget_state(config)
                    started = snap.created_at is not None
                    paused_at = snap.next[0] if snap.next and snap.next[0] in m.pause_before else None
                    if paused_at and (not update or not set(update) <= _CROSSES.get(paused_at, set())):
                        # A pause is crossed only with what it waits for — never by
                        # a bare resume (a recovery must not skip a person's sign-off).
                        return await _status_after_run(app, case_id)
                    if update:
                        await app.aupdate_state(config, update)
                    await app.ainvoke(None if started else initial_state(case, m), config)
                    status = await _status_after_run(app, case_id)
            except Exception as e:
                log.exception("case %s: run failed", case_id)
                await fail(case_id, e)
                status = "failed"
        if status == "failed":
            await _announce(case_id)
            return status
        if trace_id and kind == "open":
            async with get_session() as s:
                row = await s.get(Case, case_id)
                row.trace_id = row.trace_id or trace_id
                await s.commit()
    await _announce(case_id)
    return status


async def _announce(case_id: str) -> None:
    from helix import notify
    try:
        await notify.case_changed(case_id)
    except Exception:          # telling people must never break a run
        log.exception("case %s: notification failed", case_id)


async def submit(case_id: str, kind: str = "open", update: dict | None = None) -> None:
    """Run the case now (inline) or in the background. The caller has already
    set the case's status to "running"."""
    if settings().run_mode == "inline":
        await run_case(case_id, kind, update)
        return
    task = asyncio.create_task(run_case(case_id, kind, update), name=f"helix:{case_id}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def run_job(case_id: str, job, label: str) -> None:
    """Some other work on a paused case (e.g. re-investigating one group),
    under the same lock as a run; a failure fails the case visibly."""
    async with case_lock(case_id):
        with span(label, root=True, case_id=case_id):
            try:
                await job()
            except Exception as e:
                log.exception("case %s: %s failed", case_id, label)
                await fail(case_id, e)
    await _announce(case_id)


async def submit_job(case_id: str, job, label: str) -> None:
    if settings().run_mode == "inline":
        await run_job(case_id, job, label)
        return
    task = asyncio.create_task(run_job(case_id, job, label), name=f"helix:{case_id}:{label}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for every background run (tests, graceful shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def recover() -> list[str]:
    """At startup: finish every case left running by a stopped server."""
    async with get_session() as s:
        ids = (await s.execute(select(Case.case_id).where(
            Case.status == "running", Case.shadow_of.is_(None)))).scalars().all()
    for case_id in ids:
        await submit(case_id, "recover")
    return list(ids)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
