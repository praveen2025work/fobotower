"""Tasks: open one, run it to the review pause, take decisions, resume to record.

A task is identified by its agent and key (e.g. entity + period), so
opening the same key twice returns the existing task rather than running it
again; a failed or escalated task can be re-run, which opens attempt 2, 3…
beside it and keeps the earlier attempts as they were. A run is pinned to the
manifest active when it opened and to the caller's entitlements at that
moment. Runs happen off the request path (agent_one_finance/runner.py): every action
here records what should happen, marks the task "running" and submits it.
"""

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import String, and_, cast, func, not_, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.exc import IntegrityError

from agent_one_finance import asks, agents, deadlines, escalation, follow_through, knowledge, review, rules, runner
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Task, TaskItem, Decision, GateDecision, ProposalGroup, PublishApproval, ToolCall
from agent_one_finance.observability import span
from agent_one_finance.rules import render, template_fields


class TaskError(ValueError):
    pass


def task_id_for(agent_id: str, task_key: dict) -> str:
    digest = hashlib.sha1(json.dumps(task_key, sort_keys=True).encode()).hexdigest()[:12]
    return f"{agent_id}.{digest}"


def _check_key(m: Manifest, task_key: dict, caller: Caller) -> dict:
    missing = [k for k in m.task.key if not str(task_key.get(k, "")).strip()]
    if missing:
        raise TaskError(f"task key needs: {', '.join(missing)}")
    key = {k: str(task_key[k]).strip() for k in m.task.key}
    for field, scope in m.task.scopes.items():
        if not caller.may_see(scope, key[field]):
            raise PermissionError(f"{caller.user_id} is not entitled to {scope}={key[field]}")
    return key


def may_see_task(caller: Caller, m: Manifest, task_key: dict) -> bool:
    return agents.can_see(caller, m) and all(
        caller.may_see(scope, task_key.get(field)) for field, scope in m.task.scopes.items())


def scope_clause(caller: Caller):
    """SQL for "within the caller's data scope", from the task's scope values:
    every scope the task belongs to is one the caller holds, with its value
    in the caller's list (or the caller holds "*")."""
    dims = sorted(caller.data_scopes)
    task_scope = func.coalesce(Task.scope, cast({}, JSONB))
    clauses = [task_scope.op("-")(cast(dims, ARRAY(String))) == cast({}, JSONB)]
    for dim, allowed in sorted(caller.data_scopes.items()):
        if "*" not in allowed:
            clauses.append(or_(not_(task_scope.has_key(dim)),
                               task_scope[dim].astext.in_(sorted(allowed))))
    return and_(*clauses)


async def visible_tasks(caller: Caller, *, agent_id: str | None = None,
                        team_group: str | None = None, statuses: tuple[str, ...] | None = None,
                        limit: int | None = None, offset: int = 0, where=None) -> list[tuple[Task, Manifest]]:
    """Tasks the caller may see, newest first. Agent and data scope are
    filtered in the database (and `where`, any further SQL condition); the exact
    per-task check (`may_see_task`, on the manifest each task ran on) still runs
    on what comes back."""
    from agent_one_finance import groups as team_groups

    caps = [m.id for _, m in await agents.all_active()
            if agent_id in (None, m.id) and await team_groups.visible(caller, m.id, m)]
    if not caps:
        return []
    query = select(Task).where(Task.agent_id.in_(caps), scope_clause(caller),
                               Task.shadow_of.is_(None))     # trial runs are never on anyone's desk
    if team_group:
        query = query.where(Task.team_group == team_group)
    if where is not None:
        query = query.where(where)
    if statuses:
        # "paused_before_*" = waiting at any tollgate
        exact = [x for x in statuses if not x.endswith("*")]
        prefixes = [x[:-1] for x in statuses if x.endswith("*")]
        query = query.where(or_(Task.status.in_(exact), *[Task.status.startswith(p) for p in prefixes]))
    query = query.order_by(Task.opened_at.desc(), Task.task_id).offset(offset)
    if limit:
        query = query.limit(limit)
    async with get_session() as s:
        rows = (await s.execute(query)).scalars().all()
    out = []
    for c in rows:
        m = await _pinned(c)
        if may_see_task(caller, m, c.task_key):
            out.append((c, m))
    return out


async def _resolve_unchecked(agent_id: str, team_group: str | None) -> tuple[int, int | None, Manifest]:
    """The manifest a new run would use, before any caller check."""
    from agent_one_finance import groups as team_groups

    version, m = await agents.active(agent_id)
    if team_group:
        group_version, _, m = await team_groups.active_group(agent_id, team_group)
        return version, group_version, m
    return version, None, m


async def _resolve(agent_id: str, team_group: str | None,
                   caller: Caller) -> tuple[int, int | None, Manifest]:
    """The manifest a new run uses: the active agent version, merged with
    the active version of the chosen group when the agent has groups."""
    from agent_one_finance import groups as team_groups

    version, m = await agents.active(agent_id)
    group_version = None
    active = await team_groups.active_groups(agent_id)
    if active:
        if not team_group:
            raise TaskError(f"choose a group: {', '.join(cfg.group for _, cfg, _ in active)}")
        group_version, _, m = await team_groups.active_group(agent_id, team_group)
    elif team_group:
        raise TaskError(f"{agent_id} has no groups")
    if not agents.can_see(caller, m):
        raise PermissionError(f"{caller.user_id} has no role for {agent_id}"
                              + (f" / {team_group}" if team_group else ""))
    return version, group_version, m


async def subject_facts(m: Manifest, key: dict, given: dict | None = None) -> dict:
    """What a subject template may use besides the key: `{<field>_<fact>}`, a fact the
    reference data holds about a key value (`{book_label}` for book PRIME-MB-01, or
    `{group_name}` for FOBO group 500081), as of the task's business date. A fact it
    does not hold is taken from what the opener sent with the key (an event's
    `group_name`), else shows the key value itself."""
    wanted = [f for f in template_fields(m.task.subject or "") if f not in key]
    fields = {k for k in key for f in wanted if f.startswith(f"{k}_")}
    if not fields:
        return {}
    facts: dict = {}
    if m.knowledge.reference:
        as_of = key.get(m.knowledge.as_of) if m.knowledge.as_of else None
        nodes = await knowledge.walk(m.knowledge.reference, {f"{k}:{key[k]}" for k in fields}, [], as_of=as_of)
        for k in fields:
            node = nodes.get(f"{k}:{key[k]}")
            facts.update({f"{k}_{attr}": v for attr, v in (node.attrs if node else {}).items()})
    for f in wanted:
        k = next((k for k in fields if f.startswith(f"{k}_")), None)
        if k and f not in facts:
            facts[f] = str((given or {}).get(f) or key[k])
    return facts


def _new_task(task_id: str, root: str, attempt: int, agent_id: str, version: int,
              team_group: str | None, group_version: int | None, m: Manifest, key: dict,
              caller: Caller, rerun_of: str | None = None, facts: dict | None = None) -> Task:
    return Task(task_id=task_id, root_task_id=root, attempt=attempt, rerun_of=rerun_of,
                agent_id=agent_id, manifest_version=version,
                team_group=team_group, team_group_version=group_version,
                manifest=m.model_dump(by_alias=True), task_key=key,
                subject=render(m.task.subject or " · ".join("{" + k + "}" for k in m.task.key), {**key, **(facts or {})}),
                scope={scope: key[field] for field, scope in m.task.scopes.items()},
                status="running", opened_by=caller.user_id, run_as=caller.as_dict(),
                due_at=deadlines.due_at(m, key, datetime.now(timezone.utc)))


async def _latest_attempt(s, root: str) -> Task | None:
    return (await s.execute(select(Task).where(
        (Task.root_task_id == root) | (Task.task_id == root))
        .order_by(Task.attempt.desc()).limit(1))).scalars().first()


async def open_task(agent_id: str, task_key: dict, caller: Caller,
                    team_group: str | None = None, late: bool = False, parent: str | None = None) -> str:
    """Open a task and start its run. Opening a key that already has a task
    returns its latest attempt — unless this is a later notification (`late`)
    and the agent takes late items (`task.late_items: follow_up`): then a
    follow-up task linked to it reads the source again for what is new.
    An agent with groups runs every task under one group — its team's
    configuration — on the merged manifest."""
    version, group_version, m = await _resolve(agent_id, team_group, caller)
    await _not_switched_off(agent_id, team_group)
    key = _check_key(m, task_key, caller)
    root = task_id_for(agent_id, {**key, "__group": team_group} if team_group else key)
    facts = await subject_facts(m, key, task_key)
    async with get_session() as s:
        if (existing := await _latest_attempt(s, root)) is not None:
            if not (late and m.task.late_items == "follow_up"):
                return existing.task_id
            n = (await s.execute(select(func.count()).select_from(Task).where(
                Task.follow_up_of == root))).scalar_one() + 1
            follow = _new_task(f"{root}.f{n}", f"{root}.f{n}", 1, agent_id, version, team_group,
                               group_version, m, key, caller, facts=facts)
            follow.follow_up_of, follow.subject = root, f"{follow.subject} · late items {n}"
            s.add(follow)
            await s.commit()
            await runner.submit(follow.task_id, "open")
            return follow.task_id
        new = _new_task(root, root, 1, agent_id, version, team_group, group_version, m, key, caller, facts=facts)
        new.parent_task_id = parent        # a child task opened by a `spawn` step
        s.add(new)
        try:
            await s.commit()
        except IntegrityError:  # opened concurrently by someone else
            return root
    await runner.submit(root, "open")
    return root


async def _not_switched_off(agent_id: str, team_group: str | None) -> None:
    from agent_one_finance import controls
    try:
        await controls.check_open(agent_id, team_group)
    except controls.SwitchedOff as e:
        raise TaskError(str(e)) from e


RERUNNABLE = ("failed", "escalated", "stopped")


async def deliver_event(task_id: str, step: str, payload: dict, caller: Caller | None) -> dict:
    """An event for a task waiting at an `await` step: from a system (the
    route checked its event secret; caller is None) or from a person the step
    names (or a reviewer). The run continues with it."""
    async with get_session() as s:
        task = await s.get(Task, task_id)
    if task is None:
        raise LookupError(task_id)
    m = await _pinned(task)
    if caller is not None:
        if not may_see_task(caller, m, task.task_key):
            raise LookupError(task_id)
        cfg = m.step_config(step) if step in m.steps else None
        roles = list(getattr(cfg, "roles", []) or []) or list(m.review.roles)
        if not caller.has_any_role(roles):
            raise PermissionError(f"delivering this event needs one of: {', '.join(roles)}")
    if task.status != f"waiting_{step}":
        raise TaskError(f"task is {task.status}, not waiting at `{step}`")
    if (getattr(m.step_config(step), "event", "") == "children"):
        raise TaskError("this step waits for its child tasks; it continues when they finish")
    await runner.deliver(task_id, step, {**payload, "by": caller.user_id if caller else "system"})
    async with get_session() as s:
        return {"status": (await s.get(Task, task_id)).status}
GATE_PREFIX = "paused_before_"


def gate_step(status: str) -> str | None:
    """The step a task waits before at a tollgate, or None."""
    return status[len(GATE_PREFIX):] if status.startswith(GATE_PREFIX) else None


def may_pass_gate(caller: Caller, m: Manifest, step: str) -> bool:
    return caller.has_any_role(m.gate(step).roles)


async def pass_gate(task_id: str, step: str, action: str, comment: str | None,
                    idempotency_key: str, caller: Caller) -> dict:
    """A person at a tollgate: `continue` lets the run go on to `step`; `stop`
    ends it there (it can be re-run as a new attempt). Recorded either way."""
    if action not in ("continue", "stop"):
        raise TaskError("a tollgate is passed with continue or stop")
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        if not may_see_task(caller, m, task.task_key) and not may_pass_gate(caller, m, step):
            raise LookupError(task_id)
        existing = (await s.execute(select(GateDecision).where(
            GateDecision.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return {"replayed": True, "status": task.status}
        if gate_step(task.status) != step:
            raise TaskError(f"task is {task.status}, not waiting at the tollgate before `{step}`")
        if not may_see_task(caller, m, task.task_key) or not may_pass_gate(caller, m, step):
            raise PermissionError(f"passing this tollgate needs one of: {', '.join(m.gate(step).roles)}")
        if action == "stop" and m.gate(step).stop_needs_comment and not (comment or "").strip():
            raise TaskError("say why you stop the run: a comment is required")
        earlier = (await s.execute(select(GateDecision).where(
            GateDecision.task_id == task_id, GateDecision.action == "continue")
            .order_by(GateDecision.decided_at))).scalars().all()
        passed = [g.step for g in earlier]
        notes = [{"step": g.step, "by": g.decided_by, "comment": g.comment} for g in earlier if g.comment]
        if action == "continue" and (comment or "").strip():
            notes.append({"step": step, "by": caller.user_id, "comment": comment.strip()})
        s.add(GateDecision(gate_id=uuid.uuid4().hex, task_id=task_id, step=step, action=action,
                           comment=(comment or "").strip() or None, decided_by=caller.user_id,
                           idempotency_key=idempotency_key))
        if action == "stop":
            task.status, task.outcome = "stopped", "stopped"
            task.error = f"Stopped before `{step}` by {caller.user_id}: {(comment or '').strip()}"
        else:
            task.status = "running"
        await s.commit()
    with span("gate.decision", root=True, task_id=task_id, step=step, action=action, user=caller.user_id):
        if action == "continue":
            await runner.submit(task_id, "resume", {"gates_passed": [*passed, step], "gate_notes": notes})
        else:
            from agent_one_finance import notify
            await notify.task_changed(task_id)
    async with get_session() as s:
        status = (await s.get(Task, task_id)).status
    return {"replayed": False, "status": status}


async def rerun_task(task_id: str, caller: Caller) -> str:
    """Run a failed or escalated task again, as a new attempt on today's
    active configuration. The earlier attempt stays as it was — it is evidence."""
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None or not may_see_task(caller, await _pinned(task), task.task_key):
            raise LookupError(task_id)
        root = task.root_task_id or task.task_id
        latest = await _latest_attempt(s, root)
        if latest.task_id != task_id:
            raise TaskError(f"a newer attempt exists: {latest.task_id}")
        if task.status not in RERUNNABLE:
            raise TaskError(f"task is {task.status}; only a failed, escalated or stopped task can be re-run")
    version, group_version, m = await _resolve(task.agent_id, task.team_group, caller)
    await _not_switched_off(task.agent_id, task.team_group)
    key = _check_key(m, task.task_key, caller)
    new_id = f"{root}.r{latest.attempt + 1}"
    facts = await subject_facts(m, key)
    async with get_session() as s:
        s.add(_new_task(new_id, root, latest.attempt + 1, task.agent_id, version,
                        task.team_group, group_version, m, key, caller, rerun_of=task_id, facts=facts))
        try:
            await s.commit()
        except IntegrityError as e:
            raise TaskError("this task is already being re-run") from e
    await runner.submit(new_id, "open")
    return new_id


async def follow_ups(task: Task) -> list[dict]:
    """The follow-up tasks late items opened for this task's key."""
    root = task.follow_up_of or task.root_task_id or task.task_id
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(Task.follow_up_of == root)
                                .order_by(Task.opened_at))).scalars().all()
        counts = dict((await s.execute(select(TaskItem.task_id, func.count()).where(
            TaskItem.task_id.in_([c.task_id for c in rows])).group_by(TaskItem.task_id))).all()) if rows else {}
    return [{"task_id": c.task_id, "subject": c.subject, "status": c.status, "outcome": c.outcome,
             "opened_at": c.opened_at, "items": counts.get(c.task_id, 0)}
            for c in rows if c.task_id != task.task_id]


async def attempts(task: Task) -> list[dict]:
    root = task.root_task_id or task.task_id
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(
            (Task.root_task_id == root) | (Task.task_id == root))
            .order_by(Task.attempt))).scalars().all()
    return [{"task_id": r.task_id, "attempt": r.attempt, "status": r.status,
             "outcome": r.outcome, "opened_by": r.opened_by, "opened_at": r.opened_at} for r in rows]


def _group_env(m: Manifest, g: ProposalGroup, items: dict[str, dict]) -> dict:
    members = [items[i] for i in g.item_ids if i in items]
    amount = m.items.amount_field
    total = round(sum(float(it.get(amount) or 0) for it in members), 2) if amount else None
    return {**g.group_key, "total": total, "count": len(members), "label": g.label,
            "policy": m.policy_values()}


def _approvals_view(m: Manifest, g: ProposalGroup, decisions: list[Decision], items: dict[str, dict]) -> dict:
    """How many different people must approve, who has, and whether it is settled."""
    latest: dict[str, Decision] = {}
    for d in sorted(_since_revision(g, decisions), key=lambda d: d.decided_at):
        latest[d.decided_by] = d
    by = [u for u, d in latest.items() if d.action == "approve"]
    return {"needed": _approvals_needed(m, g, items), "by": by,
            "settled": _settle(m, g, decisions, items) is not None}


def _since_revision(g: ProposalGroup, decisions: list[Decision]) -> list[Decision]:
    """Decisions on the group's current finding — a re-investigation starts afresh."""
    revised = (g.finding or {}).get("revised_at")
    since = datetime.fromisoformat(revised) if revised else None
    return [d for d in decisions if d.group_id == g.group_id
            and (since is None or d.decided_at > since)]


def _approvals_needed(m: Manifest, g: ProposalGroup, items: dict[str, dict]) -> int:
    """Different people who must approve the group: two when `review.dual_review_when`
    holds, or what its authority tier asks for."""
    from agent_one_finance import authority
    needed = 2 if (m.review.dual_review_when and rules.evaluate(
        m.review.dual_review_when, _group_env(m, g, items))) else 1
    return max(needed, authority.approvals_needed(g.finding))


def _settle(m: Manifest, g: ProposalGroup, decisions: list[Decision],
            items: dict[str, dict]) -> dict | None:
    """The group's outcome once its reviewers are done, else None.

    Each person's latest decision counts once. A reject from anyone rejects;
    otherwise it needs one approval, or two from different people when the
    agent's `review.dual_review_when` holds for the group."""
    latest: dict[str, Decision] = {}
    for d in sorted(_since_revision(g, decisions), key=lambda d: d.decided_at):
        latest[d.decided_by] = d
    rejects = [d for d in latest.values() if d.action == "reject"]
    if rejects:
        d = rejects[-1]
        return {"group_id": g.group_id, "action": "reject", "comment": d.comment,
                "decided_by": d.decided_by, "decided_at": d.decided_at.isoformat()}
    approvals = sorted((d for d in latest.values() if d.action == "approve"),
                       key=lambda d: d.decided_at)
    needed = _approvals_needed(m, g, items)
    # Different people, counted both ways: whoever clicked, and whom they acted for.
    people = min(len({d.decided_by for d in approvals}),
                 len({d.on_behalf_of or d.decided_by for d in approvals}))
    if people < needed:
        return None
    comment = next((d.comment for d in reversed(approvals) if d.comment), None)
    return {"group_id": g.group_id, "action": "approve", "comment": comment,
            "decided_by": ", ".join(d.decided_by + (f" for {d.on_behalf_of}" if d.on_behalf_of else "")
                                    for d in approvals),
            "decided_at": approvals[-1].decided_at.isoformat()}


async def _task_items(s, task_id: str) -> dict[str, dict]:
    rows = (await s.execute(select(TaskItem).where(TaskItem.task_id == task_id))).scalars().all()
    return {r.item_id: r.payload for r in rows}


async def decide(task_id: str, group_id: str, action: str, comment: str | None,
                 idempotency_key: str, caller: Caller, confirmed: bool = False,
                 review_seconds: int | None = None, checklist: list[dict] | None = None) -> dict:
    if action not in ("approve", "reject"):
        raise TaskError("action must be approve or reject")
    comment = (comment or "").strip() or None
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        existing = (await s.execute(select(Decision).where(
            Decision.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return {"decision_id": existing.decision_id, "replayed": True, "status": task.status}
        m = await _pinned(task)
        allowed, on_behalf_of = await review.acting_as(caller, m, task.task_key, may_see_task)
        if not allowed:
            raise PermissionError(f"{caller.user_id} may not decide on this task")
        if not m.review.opener_may_decide and task.opened_by in (caller.user_id, on_behalf_of):
            raise PermissionError("maker-checker: whoever opened the task cannot sign it off")
        if task.status != "awaiting_review":
            raise TaskError(f"task is {task.status}, not awaiting review")
        group = await s.get(ProposalGroup, (task_id, group_id))
        if group is None:
            raise TaskError(f"no group {group_id!r} in this task")
        if m.requests.hold_decision and (waiting := await asks.open_on_group(task_id, group_id)):
            raise TaskError(f"a question to {waiting[0].target_name} is still open; "
                            "wait for the answer or cancel the question")
        escalated = (group.finding or {}).get("status") == "escalated"
        if comment is None and action == "reject" and "reject" in m.review.require_comment:
            raise TaskError("say why you reject it: a comment is required")
        if comment is None and action == "approve" and escalated \
                and "escalated" in m.review.require_comment:
            raise TaskError("this group was escalated: approving it needs your explanation")
        if why := review.confirmation_problem(m, group.finding, action, confirmed, comment):
            raise TaskError(why)
        from agent_one_finance import authority
        if why := authority.may_decide(group.finding, caller):
            raise PermissionError(why)
        from agent_one_finance import checklist as sign_off
        try:
            answers = sign_off.answered(m, action, checklist)
        except sign_off.ChecklistError as e:
            raise TaskError(str(e)) from None
        decision = Decision(decision_id=uuid.uuid4().hex, task_id=task_id, group_id=group_id,
                            action=action, comment=comment, decided_by=caller.user_id,
                            idempotency_key=idempotency_key,
                            confirmed=bool(confirmed and action == "approve"),
                            on_behalf_of=on_behalf_of, checklist=answers,
                            review_seconds=(max(0, min(int(review_seconds), 8 * 3600))
                                            if review_seconds is not None else None))
        s.add(decision)
        await s.commit()

    with span("review.decision", root=True, task_id=task_id, group_id=group_id, action=action,
              user=caller.user_id):
        status = await _resume_if_complete(task_id, m)
    return {"decision_id": decision.decision_id, "replayed": False, "status": status}


async def bulk_decide(task_id: str, group_ids: list[str], action: str, comment: str | None,
                      idempotency_key: str, caller: Caller, review_seconds: int | None = None,
                      checklist: list[dict] | None = None, confirmed: bool = False) -> dict:
    """The same decision on many groups — "Approve all", or the proposals a reviewer
    selected. Each is checked on its own: an escalated group without a comment is
    refused while the others go through. Approving in bulk leaves the groups the
    agent marks for one-by-one review (review.bulk_exclude: e.g. a verdict needing
    confirmation, a judgement call); `confirmed` confirms the verdicts of the others
    that need it."""
    done, refused = [], []
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        findings = {g.group_id: g.finding for g in (await s.execute(select(ProposalGroup).where(
            ProposalGroup.task_id == task_id))).scalars()}
    for gid in dict.fromkeys(group_ids):
        if action == "approve" and (why := review.bulk_blockers(m, findings.get(gid))):
            refused.append({"group_id": gid, "reason": "needs one-by-one review: " + ", ".join(
                _FLAG_WORDS[f] for f in why)})
            continue
        try:
            share = round(review_seconds / max(1, len(group_ids))) if review_seconds is not None else None
            r = await decide(task_id, gid, action, comment, f"{idempotency_key}:{gid}", caller,
                             confirmed=confirmed, review_seconds=share, checklist=checklist)
            done.append({"group_id": gid, **r})
        except (TaskError, PermissionError) as e:
            refused.append({"group_id": gid, "reason": str(e)})
    async with get_session() as s:
        status = (await s.get(Task, task_id)).status
    return {"decided": done, "refused": refused, "status": status}


_pinned = runner.pinned

_FLAG_WORDS = {"confirmation": "the verdict needs your confirmation",
               "judgement": "a judgement call", "escalated": "escalated", "model": "proposed by the model",
               "reserved": "a decision reserved for named people", "authority": "its authority tier needs one-by-one review"}


async def reinvestigate(task_id: str, group_id: str, note: str, idempotency_key: str,
                        caller: Caller) -> dict:
    """A reviewer sends one group back to the model with a note. The new
    finding goes through the same grounding check; decisions already taken on
    the group no longer count — it is reviewed afresh."""
    from agent_one_finance import steps
    from agent_one_finance.workflow import build_graph, checkpointer

    note = (note or "").strip()
    if not note:
        raise TaskError("say what to look at again: a note is required")
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        if not (await review.acting_as(caller, m, task.task_key, may_see_task))[0]:
            raise PermissionError(f"{caller.user_id} may not review this task")
        group = await s.get(ProposalGroup, (task_id, group_id))
        if group is None:
            raise TaskError(f"no group {group_id!r} in this task")
        previous = dict(group.finding or {})
        if idempotency_key in previous.get("reinvestigation_keys", []):
            return {"replayed": True, "status": task.status}
        if task.status != "awaiting_review":
            raise TaskError(f"task is {task.status}, not awaiting review")
        if m.reasoning.reasoner != "llm":
            raise TaskError("this agent has no model to investigate again")
        done = previous.get("reinvestigations", 0)
        if done >= m.review.max_reinvestigations:
            raise TaskError(f"this group was already sent back {done} time(s), the limit")
        task.status = "running"
        await s.commit()

    async def job():
        config = {"configurable": {"thread_id": f"aof:{task_id}"}}
        async with checkpointer() as cp:
            app = build_graph(m.steps, m.pause_before, cp, m.step_types())
            state = (await app.aget_state(config)).values
            g = next(x for x in state["groups"] if x["group_id"] == group_id)
            finding = await steps.reason_group(state, g, note, previous)
            missing = steps.ungrounded(finding.get("comment", ""), await steps.grounded_figures(state))
            if finding["status"] == "proposed" and missing:
                finding = {**finding, "status": steps.ESCALATED,
                           "reason": f"UNGROUNDED_FIGURE: {', '.join(f'{n:,.2f}' for n in missing)}"}
            async with get_session() as s:
                now = (await s.execute(select(func.now()))).scalar_one()
            finding.update({
                "revised_at": now.isoformat(), "reinvestigations": done + 1,
                "reviewer_note": note, "requested_by": caller.user_id,
                "reinvestigation_keys": [*previous.get("reinvestigation_keys", []), idempotency_key],
                "previous": {k: previous.get(k) for k in ("status", "comment", "reason", "decided_by")}})
            await app.aupdate_state(config, {"findings": {**state["findings"], group_id: finding}})
        async with get_session() as s:
            row = await s.get(ProposalGroup, (task_id, group_id))
            row.finding = finding
            c = await s.get(Task, task_id)
            if c.draft:
                c.draft = {**c.draft, "groups": [
                    {**x, "comment": finding.get("comment", "")} if x["group_id"] == group_id else x
                    for x in c.draft.get("groups", [])]}
            c.status = "awaiting_review"
            await s.commit()

    await runner.submit_job(task_id, job, "review.reinvestigate")
    async with get_session() as s:
        return {"replayed": False, "status": (await s.get(Task, task_id)).status}


def _latest(decisions: list[Decision]) -> dict[str, Decision]:
    out: dict[str, Decision] = {}
    for d in sorted(decisions, key=lambda d: d.decided_at):
        out[d.group_id] = d
    return out


async def _resume_if_complete(task_id: str, m: Manifest) -> str:
    """When every group is settled, hand the outcomes to the run and resume it."""
    async with get_session() as s:
        groups = (await s.execute(select(ProposalGroup).where(
            ProposalGroup.task_id == task_id))).scalars().all()
        decisions = (await s.execute(select(Decision).where(
            Decision.task_id == task_id))).scalars().all()
        items = await _task_items(s, task_id)
        settled = [_settle(m, g, decisions, items) for g in groups]
        task = await s.get(Task, task_id)
        if any(x is None for x in settled) or task.status != "awaiting_review":
            return task.status
        task.status = "running"
        await s.commit()
    await runner.submit(task_id, "resume", {"decisions": settled})
    async with get_session() as s:
        return (await s.get(Task, task_id)).status


async def approve_publish(task_id: str, idempotency_key: str, caller: Caller) -> dict:
    """A second person releases the write-back. Four-eyes: nobody who signed
    off a group in this task may release it."""
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        if not may_see_task(caller, m, task.task_key):
            raise LookupError(task_id)
        existing = await s.get(PublishApproval, task_id)
        if existing is not None:
            if existing.idempotency_key == idempotency_key:
                return {"replayed": True, "status": task.status}
            raise TaskError("write-back was already released")
        if m.release_step() is None or task.status != "awaiting_publish":
            raise TaskError(f"task is {task.status}, not awaiting publish")
        if not caller.has_any_role(m.release_roles()):
            raise PermissionError(f"{caller.user_id} may not release write-back")
        if caller.user_id in await _deciders(s, task_id):
            raise PermissionError("four-eyes: a reviewer of this task cannot release its write-back")
        approval = PublishApproval(task_id=task_id, approved_by=caller.user_id,
                                   idempotency_key=idempotency_key)
        s.add(approval)
        task.status = "running"
        await s.commit()
    with span("publish.approval", root=True, task_id=task_id, user=caller.user_id):
        await runner.submit(task_id, "publish", {"publish_approval": {
            "approved_by": caller.user_id, "approved_at": runner.now_iso()}})
    async with get_session() as s:
        status = (await s.get(Task, task_id)).status
    return {"replayed": False, "status": status}


async def retry_publish(task_id: str, caller: Caller) -> dict:
    """Finish a write-back that failed part-way: only the writes that did not
    land are sent again, each with its original idempotency key. Same rules as
    the release — a publish approver who did not review the task."""
    from agent_one_finance import steps
    from agent_one_finance.workflow import build_graph, checkpointer

    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        if not may_see_task(caller, m, task.task_key):
            raise LookupError(task_id)
        if m.publish is None or task.outcome != "publish_failed":
            raise TaskError(f"task is {task.status}/{task.outcome}; nothing to retry")
        if not caller.has_any_role(m.publish.approver_roles):
            raise PermissionError(f"{caller.user_id} may not release write-back")
        if caller.user_id in await _deciders(s, task_id):
            raise PermissionError("four-eyes: a reviewer of this task cannot release its write-back")
        done = frozenset((await s.execute(select(ToolCall.idempotency_key).where(
            ToolCall.task_id == task_id, ToolCall.requested_by == "publish",
            ToolCall.allowed.is_(True), ToolCall.error.is_(None),
            ToolCall.idempotency_key.is_not(None)))).scalars())
        task.status = "running"
        await s.commit()

    async def job():
        config = {"configurable": {"thread_id": f"aof:{task_id}"}}
        async with checkpointer() as cp:
            state = (await build_graph(m.steps, m.pause_before, cp, m.step_types()).aget_state(config)).values
        _, failed = await steps.write_back(state, caller.user_id, done)
        await steps.set_publish_outcome(task_id, failed)

    await runner.submit_job(task_id, job, "publish.retry")
    async with get_session() as s:
        c = await s.get(Task, task_id)
        return {"status": c.status, "outcome": c.outcome, "skipped": sorted(done)}


async def _deciders(s, task_id: str) -> set[str]:
    return set((await s.execute(select(Decision.decided_by).where(
        Decision.task_id == task_id))).scalars())


# ---------- reads ----------

def _task_summary(c: Task) -> dict:
    return {"task_id": c.task_id, "agent_id": c.agent_id, "subject": c.subject,
            "task_key": c.task_key, "status": c.status, "outcome": c.outcome,
            "manifest_version": c.manifest_version, "team_group": c.team_group,
            "team_group_version": c.team_group_version, "opened_by": c.opened_by,
            "opened_at": c.opened_at, "trace_id": c.trace_id, "error": c.error,
            "attempt": c.attempt or 1, "rerun_of": c.rerun_of, "legal_hold": bool(c.legal_hold),
            "due_at": c.due_at, "review_ready_at": c.review_ready_at,
            "follow_up_of": c.follow_up_of}


async def list_tasks(agent_id: str, caller: Caller, team_group: str | None = None,
                     limit: int = 200, offset: int = 0) -> list[dict]:
    from agent_one_finance import groups as team_groups

    _, m = await agents.active(agent_id)
    if not await team_groups.visible(caller, agent_id, m):
        raise PermissionError(f"{caller.user_id} has no role for {agent_id}")
    return [_task_summary(c) for c, _ in await visible_tasks(
        caller, agent_id=agent_id, team_group=team_group, limit=limit, offset=offset)]


SHOWN_ROWS = 100      # rows of a tool's result a task page shows; the audit record keeps every row


def _shown(result):
    """A tool result as the task page shows it: a source read for a whole region
    (thousands of positions) is cut to its first rows, and says so."""
    rows = result.get("rows") if isinstance(result, dict) else None
    if isinstance(rows, list) and len(rows) > SHOWN_ROWS:
        return {**result, "rows": rows[:SHOWN_ROWS], "rows_shown": SHOWN_ROWS}
    return result


def _documents(task_id: str, calls: list[ToolCall]) -> list[dict]:
    """Reports this task's publish step wrote (a write tool's receipt that names a document)."""
    out = []
    for c in calls:
        r = c.result if isinstance(c.result, dict) else {}
        if c.requested_by == "publish" and c.allowed and not c.error and r.get("document"):
            out.append({"name": r["document"], "tool": c.tool, "pages": r.get("pages"),
                        "bytes": r.get("bytes"), "sha256": r.get("sha256"),
                        "written_at": c.called_at,
                        "url": f"/api/tasks/{task_id}/documents/{r['document']}"})
    return out


async def _evidence(task_id: str) -> list[dict]:
    from agent_one_finance import evidence
    return await evidence.for_task(task_id)


async def published_document(task_id: str, name: str, caller: Caller) -> tuple[str, str]:
    """(scope, name) of a report this task published, if the caller may see the task."""
    detail = await task_detail(task_id, caller)          # LookupError if not visible
    for c in detail["tool_calls"]:
        r = c["result"] if isinstance(c["result"], dict) else {}
        if c["requested_by"] == "publish" and c["allowed"] and r.get("document") == name:
            return r["scope"], name
    raise LookupError(f"{task_id}/{name}")


async def _reports(task_id: str) -> list[dict]:
    """Reports a `report` step kept with the task (its PDF), newest last."""
    from agent_one_finance.models import Document
    async with get_session() as s:
        rows = (await s.execute(select(Document.name, Document.sha256, Document.created_at, func.length(Document.content))
                                .where(Document.task_id == task_id, Document.kind == "report")
                                .order_by(Document.created_at))).all()
    return [{"name": n, "tool": "report", "pages": None, "bytes": size, "sha256": sha, "written_at": at,
             "url": f"/api/tasks/{task_id}/documents/{n}"} for n, sha, at, size in rows]


async def task_report(task_id: str, name: str, caller: Caller) -> tuple[bytes, str] | None:
    """A report a `report` step kept with the task, if the caller may see the task."""
    from agent_one_finance.models import Document
    await task_detail(task_id, caller)                    # LookupError if not visible
    async with get_session() as s:
        row = (await s.execute(select(Document).where(Document.task_id == task_id, Document.kind == "report",
                                                      Document.name == name))).scalar_one_or_none()
    return (row.content, row.content_type) if row else None


async def _datasets(task_id: str) -> list[dict]:
    from agent_one_finance.models import TaskDataset
    async with get_session() as s:
        rows = (await s.execute(select(TaskDataset).where(TaskDataset.task_id == task_id)
                                .order_by(TaskDataset.created_at))).scalars().all()
    return [{"name": d.name, "step_id": d.step_id, "source": d.source, "row_count": d.row_count,
             "columns": sorted({k for r in d.rows[:200] for k in r if k != "members"}),
             "rows": d.rows[:100]} for d in rows]


async def task_detail(task_id: str, caller: Caller) -> dict:
    async with get_session() as s:
        task = await s.get(Task, task_id)
        if task is None:
            raise LookupError(task_id)
        m = await _pinned(task)
        may_decide, on_behalf_of = await review.acting_as(caller, m, task.task_key, may_see_task)
        if not may_see_task(caller, m, task.task_key) and not may_decide:
            # Same answer as a missing task: a caller cannot tell the difference.
            raise LookupError(task_id)
        items = (await s.execute(select(TaskItem).where(TaskItem.task_id == task_id)
                                 .order_by(TaskItem.item_id))).scalars().all()
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.task_id == task_id)
                                  .order_by(ProposalGroup.group_id))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.task_id == task_id)
                                     .order_by(Decision.decided_at))).scalars().all()
        calls = (await s.execute(select(ToolCall).where(ToolCall.task_id == task_id)
                                 .order_by(ToolCall.called_at))).scalars().all()
        release = await s.get(PublishApproval, task_id)
        gates = (await s.execute(select(GateDecision).where(GateDecision.task_id == task_id)
                                 .order_by(GateDecision.decided_at))).scalars().all()
    latest = _latest(decisions)
    in_group = {i for g in groups for i in g.item_ids}
    tickets = await escalation.for_task(task_id)
    from agent_one_finance import insights
    recurring = await insights.recurring_for_task(task, m, sorted(in_group))
    now = datetime.now(timezone.utc)
    from agent_one_finance import checklist
    items_by = {it.item_id: it.payload for it in items}
    evidence_rows = await _evidence(task_id)
    requests = await asks.for_task(task_id, caller)
    return {
        **_task_summary(task),
        "due_state": deadlines.state(task.due_at, task.status, now,
                                     m.task.due.warn_hours if m.task.due else 2),
        "exposure": (task.draft or {}).get("exposure"), "unit": m.items.amount_unit,
        "id_field": m.items.id_field, "amount_field": m.items.amount_field,
        "recurring": recurring,
        "attempts": await attempts(task),
        "follow_ups": await follow_ups(task),
        # What became of this task's decisions in the next run (follow_through).
        "follow_through": (await follow_through.for_task(task_id)) if m.follow_through else None,
        # Named data sets the run read or built beside the items (dataset, aggregate steps).
        "datasets": await _datasets(task_id),
        # Items a step set aside (filter, dedupe, roll-up): still on the task, with the reason.
        "excluded": [{"item_id": it.item_id, "by": it.payload.get("excluded_by"),
                      "reason": it.payload.get("excluded_reason")}
                     for it in items if it.payload.get("excluded_by")],
        "step_labels": {sid: (st.label or m.step_type(sid)) for sid, st in m.step_settings.items()},
        "step_types": {sid: m.step_type(sid) for sid in m.step_settings},
        "follow_through_spec": m.follow_through.model_dump() if m.follow_through else None,
        "requests": requests,
        "request_targets": [{"id": t.id, "name": t.name} for t in m.requests.targets],
        "can_ask": bool(m.requests.targets) and (
            (may_decide and task.status == "awaiting_review")
            or bool((st := gate_step(task.status)) and may_pass_gate(caller, m, st))),
        "draft": task.draft,
        "labels": {"task": m.task.label, "item": m.task.item_label, "agent": m.name},
        "summarize_by": m.task.summarize_by,
        "steps": m.steps, "pause_before": m.pause_before,
        "columns": m.items.display or sorted({k for it in items for k in it.payload}),
        "items": [{"item_id": it.item_id, "in_scope": it.item_id in in_group,
                   **it.payload} for it in items],
        "groups": [{
            "group_id": g.group_id, "label": g.label, "group_key": g.group_key,
            "item_ids": g.item_ids, "priors": g.priors, "finding": g.finding,
            "flags": review.flags(g.finding),
            "ticket": tickets.get(g.group_id),
            "bulk_blockers": review.bulk_blockers(m, g.finding),
            "checklist": checklist.known(m, g.finding, [items_by[i] for i in g.item_ids if i in items_by],
                                         evidence_rows, [r for r in requests
                                                         if r["status"] == "answered" and r["group_id"] in (None, g.group_id)])
            if m.review.checklist else None,
            "decision": ({"action": latest[g.group_id].action,
                          "comment": latest[g.group_id].comment,
                          "decided_by": latest[g.group_id].decided_by,
                          "on_behalf_of": latest[g.group_id].on_behalf_of,
                          "confirmed": latest[g.group_id].confirmed,
                          "checklist": latest[g.group_id].checklist,
                          "decided_at": latest[g.group_id].decided_at}
                         if g.group_id in latest else None),
            "approvals": _approvals_view(m, g, decisions, items_by),
        } for g in groups],
        "decisions": [{"group_id": d.group_id, "action": d.action, "comment": d.comment,
                       "decided_by": d.decided_by, "on_behalf_of": d.on_behalf_of,
                       "confirmed": d.confirmed, "decided_at": d.decided_at}
                      for d in decisions],
        "tool_calls": [{"call_id": c.call_id, "tool": c.tool, "connector_id": c.connector_id,
                        "requested_by": c.requested_by, "caller": c.caller,
                        "arguments": c.arguments, "allowed": c.allowed,
                        "denied_reason": c.denied_reason, "row_count": c.row_count,
                        "error": c.error, "latency_ms": c.latency_ms, "called_at": c.called_at,
                        "result": _shown(c.result)} for c in calls],
        "documents": _documents(task_id, calls) + await _reports(task_id),
        "evidence": evidence_rows,
        "can_decide": (may_decide and task.status == "awaiting_review"
                       and (m.review.opener_may_decide
                            or task.opened_by not in (caller.user_id, on_behalf_of))),
        "acting_for": on_behalf_of,
        "can_rerun": task.status in RERUNNABLE and agents.can_see(caller, m),
        "can_hold": agents.is_owner(caller, m),
        "legal_hold_reason": task.legal_hold_reason,
        "can_retry_publish": (task.outcome == "publish_failed" and m.publish is not None
                              and caller.has_any_role(m.publish.approver_roles)
                              and caller.user_id not in {d.decided_by for d in decisions}),
        "review": {"require_comment": m.review.require_comment,
                   "opener_may_decide": m.review.opener_may_decide,
                   "dual_review_when": m.review.dual_review_when,
                   "max_reinvestigations": m.review.max_reinvestigations,
                   "roles": list(m.review.roles),
                   "bulk_exclude": m.review.bulk_exclude, "confirm": m.review.confirm,
                   "allow_delegation": m.review.allow_delegation,
                   "checklist": [q.model_dump() for q in m.review.checklist]},
        "publish": ({"tool": m.publish.tool if m.publish else m.release_step(), "approver_roles": m.release_roles(),
                     "per": m.publish.per if m.publish else "task",
                     "can_release": (task.status == "awaiting_publish"
                                     and caller.has_any_role(m.release_roles())
                                     and caller.user_id not in {d.decided_by for d in decisions}),
                     "released": ({"by": release.approved_by, "at": release.approved_at} if release else None)}
                    if m.release_step() else None),
        # Who the task waits on, and — when it is not this caller — why not, in plain words.
        "waiting_on": _waiting_on(task, m, caller, decisions, may_decide, on_behalf_of),
        "tollgates": [{"step": st, "roles": m.gate(st).roles, "check": m.gate(st).check}
                      for st in m.pause_before if st not in ("review", "publish")],
        "gate_decisions": [{"step": g.step, "action": g.action, "comment": g.comment,
                            "decided_by": g.decided_by, "decided_at": g.decided_at} for g in gates],
        # steps v2: the task this one was opened for, the tasks it opened, its clocks
        "parent_task_id": task.parent_task_id,
        "children": await _children(task_id),
        "clocks": [{"id": k, **v} for k, v in (task.clock_state or {}).items()],
    }


async def _children(task_id: str) -> list[dict]:
    async with get_session() as s:
        kids = (await s.execute(select(Task).where(Task.parent_task_id == task_id)
                                .order_by(Task.opened_at))).scalars().all()
    return [{"task_id": k.task_id, "subject": k.subject, "status": k.status, "outcome": k.outcome,
             "agent_id": k.agent_id} for k in kids]


def _waiting_on(task: Task, m: Manifest, caller: Caller, decisions: list[Decision],
                may_decide: bool, on_behalf_of: str | None) -> dict | None:
    deciders = {d.decided_by for d in decisions}
    if step := gate_step(task.status):
        gate = m.gate(step)
        why_not = None if may_pass_gate(caller, m, step) else f"passing this tollgate needs one of: {', '.join(gate.roles)}"
        return {"step": "gate", "gate": step, "roles": list(gate.roles), "check": gate.check,
                "stop_needs_comment": gate.stop_needs_comment, "you": why_not is None, "why_not": why_not}
    if task.status == "awaiting_review":
        why_not = None
        if not may_decide:
            why_not = f"reviewing needs one of: {', '.join(m.review.roles)}"
        elif not m.review.opener_may_decide and task.opened_by in (caller.user_id, on_behalf_of):
            why_not = "you opened this task, and its agent needs someone else to sign it off"
        return {"step": "review", "roles": list(m.review.roles), "you": why_not is None, "why_not": why_not}
    if task.status.startswith("waiting_") and task.status[8:] in m.steps:
        step = task.status[8:]
        cfg = m.step_config(step)
        event = getattr(cfg, "event", "")
        roles = list(getattr(cfg, "roles", []) or []) or list(m.review.roles)
        by_hand = event != "children" and caller.has_any_role(roles)
        return {"step": "event", "event": event, "wait": step, "label": (m.step_settings[step].label if step in m.step_settings else None) or step,
                "since": task.waiting_since, "timeout_hours": getattr(cfg, "timeout_hours", None),
                "on_timeout": getattr(cfg, "on_timeout", None), "roles": roles, "you": by_hand,
                "why_not": None if by_hand else ("it continues when every child task has finished" if event == "children"
                                                 else f"delivering it by hand needs one of: {', '.join(roles)}")}
    if task.status == "awaiting_publish" and m.release_step():
        why_not = None
        if not caller.has_any_role(m.release_roles()):
            why_not = f"releasing needs one of: {', '.join(m.release_roles())}"
        elif caller.user_id in deciders:
            why_not = "you reviewed this task; a second person who did not review it releases it"
        return {"step": "release", "roles": list(m.release_roles()), "you": why_not is None,
                "why_not": why_not, "reviewed_by": sorted(deciders)}
    return None
