"""Workflow versions — the database decides which workflow runs.

The checked-in YAML seeds version 1. After that the workflow changes only
through a draft that a *second* Product Control user approves; approval
activates it for new runs, and a run keeps the version it started with
(app/workflow/graph.py). Nothing is ever deleted.

Every rule here is enforced server-side; the Workflow tab only reflects them.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.db.models_workflow import WorkflowVersion
from app.workflow.config import (
    REPO_ROOT,
    WorkflowConfig,
    dump_config,
    errors_of,
    read_workflow,
    workflow_path,
)

SYSTEM = "system"
PC_ROLE = "PC"
NOTE_MAX = 500
# Distinct from api/deps.py SEED_LOCK_KEY (872155).
WORKFLOW_LOCK_KEY = 872156


class VersionError(Exception):
    status = 400


class NotAllowed(VersionError):
    status = 403


class NotFound(VersionError):
    status = 404


class Conflict(VersionError):
    status = 409


class Invalid(VersionError):
    status = 422

    def __init__(self, message: str, errors=()):
        super().__init__(message)
        self.errors = list(errors)


@dataclass(frozen=True)
class Pinned:
    number: int
    config: WorkflowConfig


@lru_cache(maxsize=64)
def _validated(config_json: str) -> WorkflowConfig:
    return WorkflowConfig.model_validate(json.loads(config_json))


def as_config(raw: dict) -> WorkflowConfig:
    """Validated config for stored JSON. Cached by content, so a version's
    config is validated once per process however often it is read."""
    return _validated(json.dumps(raw, sort_keys=True))


def validation_errors(raw) -> list[str]:
    try:
        WorkflowConfig.model_validate(raw)
    except (ValidationError, ValueError) as exc:
        return errors_of(exc)
    return []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_note() -> str:
    path = workflow_path()
    try:
        shown = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = path
    return f"seeded from {shown}"


async def _lock(s) -> None:
    """Transaction-scoped: released by the commit or rollback that ends it."""
    await s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": WORKFLOW_LOCK_KEY})


async def _count(s) -> int:
    return await s.scalar(select(func.count()).select_from(WorkflowVersion))


async def ensure_seeded(s) -> None:
    if await _count(s):
        return
    await _lock(s)
    if not await _count(s):
        now = _now()
        s.add(WorkflowVersion(
            number=1, config=dump_config(read_workflow()), status="active",
            based_on=None, note=_seed_note(), drafted_by=SYSTEM, drafted_at=now,
            decided_by=SYSTEM, decided_at=now,
        ))
    await s.commit()


async def get(s, number: int) -> WorkflowVersion:
    row = await s.get(WorkflowVersion, number)
    if row is None:
        raise NotFound(f"no workflow version {number}")
    return row


async def _active_row(s) -> WorkflowVersion:
    """Fresh, not the identity map's copy: with expire_on_commit=False, a
    session that already holds this row gets its own pre-existing in-memory
    object back, unrefreshed, unless asked to repopulate it — and a decision
    made under the advisory lock must see what another session just
    committed, not what this session saw before the lock was acquired."""
    return await s.scalar(
        select(WorkflowVersion)
        .where(WorkflowVersion.status == "active")
        .execution_options(populate_existing=True)
    )


async def active(s) -> Pinned:
    await ensure_seeded(s)
    row = await _active_row(s)
    if row is None:
        raise Conflict("no workflow version is active")
    return Pinned(row.number, as_config(row.config))


async def pinned(s, number: int) -> Pinned:
    await ensure_seeded(s)
    return Pinned(number, as_config((await get(s, number)).config))


async def config_for(s, number: int | None) -> WorkflowConfig:
    """A run's workflow. None: the run predates versioning — version 1."""
    return (await pinned(s, number or 1)).config


async def list_versions(s) -> list[WorkflowVersion]:
    await ensure_seeded(s)
    rows = await s.scalars(select(WorkflowVersion).order_by(WorkflowVersion.number.desc()))
    return list(rows.all())


async def pending_count(s) -> int:
    return await s.scalar(
        select(func.count()).select_from(WorkflowVersion).where(WorkflowVersion.status == "draft"))


def _require_pc(caller) -> None:
    if PC_ROLE not in caller.roles:
        raise NotAllowed("only Product Control can change the workflow")


def _clean_note(note: str | None) -> str:
    n = (note or "").strip()
    if not n:
        raise Invalid("a note is required: say why the workflow is changing")
    if len(n) > NOTE_MAX:
        raise Invalid(f"the note is {len(n)} characters; the limit is {NOTE_MAX}")
    return n


async def create_draft(s, *, raw: dict, note: str, based_on: int, caller) -> WorkflowVersion:
    _require_pc(caller)
    clean = _clean_note(note)
    errors = validation_errors(raw)
    if errors:
        raise Invalid("workflow is invalid", errors)
    await ensure_seeded(s)
    await get(s, based_on)
    await _lock(s)
    number = (await s.scalar(select(func.max(WorkflowVersion.number)))) + 1
    row = WorkflowVersion(
        number=number, config=dump_config(WorkflowConfig.model_validate(raw)),
        status="draft", based_on=based_on, note=clean,
        drafted_by=caller.staff_id, drafted_at=_now(),
    )
    s.add(row)
    await s.commit()
    return row


async def _decidable(s, number: int) -> WorkflowVersion:
    """Fresh, not the identity map's copy — see `_active_row`. A caller that
    already holds this row (e.g. it read it before calling approve/reject)
    would otherwise have its decision judged against the status it saw
    before the advisory lock was acquired, not the status a competing,
    already-committed decision just gave it."""
    row = await s.get(WorkflowVersion, number, populate_existing=True)
    if row is None:
        raise NotFound(f"no workflow version {number}")
    if row.status != "draft":
        raise Conflict(f"v{number} is {row.status}, not a draft")
    return row


async def approve(s, number: int, *, caller, key: str) -> WorkflowVersion:
    _require_pc(caller)
    if not (key or "").strip():
        raise Invalid("an Idempotency-Key header is required")
    if len(key) > 128:
        raise Invalid("the Idempotency-Key is longer than 128 characters")
    await _lock(s)
    used = await s.scalar(select(WorkflowVersion.number).where(WorkflowVersion.decision_key == key))
    if used is not None:
        raise Conflict("this approval was already recorded")
    row = await _decidable(s, number)
    if row.drafted_by == caller.staff_id:
        raise NotAllowed("a second Product Control user must approve — you drafted this version")
    current = await _active_row(s)
    if current.number != row.based_on:
        raise Conflict(f"v{current.number} went live after this was drafted — "
                       f"redraft it on v{current.number}")
    current.status = "superseded"
    # Flush first: the partial unique index allows one active row at a time.
    await s.flush()
    row.status, row.decided_by, row.decided_at, row.decision_key = (
        "active", caller.staff_id, _now(), key)
    await s.commit()
    return row


async def reject(s, number: int, *, caller, reason: str) -> WorkflowVersion:
    _require_pc(caller)
    clean = (reason or "").strip()
    if not clean:
        raise Invalid("a rejection requires a reason")
    await _lock(s)
    row = await _decidable(s, number)
    row.status, row.decided_by, row.decided_at, row.reject_reason = (
        "rejected", caller.staff_id, _now(), clean)
    await s.commit()
    return row


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def view(row: WorkflowVersion, *, with_config: bool = True) -> dict:
    body = {
        "number": row.number,
        "status": row.status,
        "note": row.note,
        "based_on": row.based_on,
        "drafted_by": row.drafted_by,
        "drafted_at": _iso(row.drafted_at),
        "decided_by": row.decided_by,
        "decided_at": _iso(row.decided_at),
        "reject_reason": row.reject_reason,
    }
    if with_config:
        # Re-dumped through the model: JSONB does not keep key order.
        body["config"] = dump_config(as_config(row.config))
    return body
