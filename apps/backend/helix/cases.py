"""Cases: open one, run it to the review pause, take decisions, resume to record.

A case is identified by its capability and key (e.g. entity + period), so
opening the same key twice returns the existing case rather than running it
again; a failed or escalated case can be re-run, which opens attempt 2, 3…
beside it and keeps the earlier attempts as they were. A run is pinned to the
manifest active when it opened and to the caller's entitlements at that
moment. Runs happen off the request path (helix/runner.py): every action
here records what should happen, marks the case "running" and submits it.
"""

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import String, and_, cast, func, not_, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.exc import IntegrityError

from helix import asks, capabilities, deadlines, escalation, follow_through, review, rules, runner
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import Case, CaseItem, Decision, GateDecision, ProposalGroup, PublishApproval, ToolCall
from helix.observability import span
from helix.rules import render


class CaseError(ValueError):
    pass


def case_id_for(capability_id: str, case_key: dict) -> str:
    digest = hashlib.sha1(json.dumps(case_key, sort_keys=True).encode()).hexdigest()[:12]
    return f"{capability_id}.{digest}"


def _check_key(m: Manifest, case_key: dict, caller: Caller) -> dict:
    missing = [k for k in m.case.key if not str(case_key.get(k, "")).strip()]
    if missing:
        raise CaseError(f"case key needs: {', '.join(missing)}")
    key = {k: str(case_key[k]).strip() for k in m.case.key}
    for field, scope in m.case.scopes.items():
        if not caller.may_see(scope, key[field]):
            raise PermissionError(f"{caller.user_id} is not entitled to {scope}={key[field]}")
    return key


def may_see_case(caller: Caller, m: Manifest, case_key: dict) -> bool:
    return capabilities.can_see(caller, m) and all(
        caller.may_see(scope, case_key.get(field)) for field, scope in m.case.scopes.items())


def scope_clause(caller: Caller):
    """SQL for "within the caller's data scope", from the case's scope values:
    every scope the case belongs to is one the caller holds, with its value
    in the caller's list (or the caller holds "*")."""
    dims = sorted(caller.data_scopes)
    case_scope = func.coalesce(Case.scope, cast({}, JSONB))
    clauses = [case_scope.op("-")(cast(dims, ARRAY(String))) == cast({}, JSONB)]
    for dim, allowed in sorted(caller.data_scopes.items()):
        if "*" not in allowed:
            clauses.append(or_(not_(case_scope.has_key(dim)),
                               case_scope[dim].astext.in_(sorted(allowed))))
    return and_(*clauses)


async def visible_cases(caller: Caller, *, capability_id: str | None = None,
                        team_group: str | None = None, statuses: tuple[str, ...] | None = None,
                        limit: int | None = None, offset: int = 0) -> list[tuple[Case, Manifest]]:
    """Cases the caller may see, newest first. Capability and data scope are
    filtered in the database; the exact per-case check (`may_see_case`, on the
    manifest each case ran on) still runs on what comes back."""
    from helix import groups as team_groups

    caps = [m.id for _, m in await capabilities.all_active()
            if capability_id in (None, m.id) and await team_groups.visible(caller, m.id, m)]
    if not caps:
        return []
    query = select(Case).where(Case.capability_id.in_(caps), scope_clause(caller),
                               Case.shadow_of.is_(None))     # trial runs are never on anyone's desk
    if team_group:
        query = query.where(Case.team_group == team_group)
    if statuses:
        # "paused_before_*" = waiting at any tollgate
        exact = [x for x in statuses if not x.endswith("*")]
        prefixes = [x[:-1] for x in statuses if x.endswith("*")]
        query = query.where(or_(Case.status.in_(exact), *[Case.status.startswith(p) for p in prefixes]))
    query = query.order_by(Case.opened_at.desc(), Case.case_id).offset(offset)
    if limit:
        query = query.limit(limit)
    async with get_session() as s:
        rows = (await s.execute(query)).scalars().all()
    out = []
    for c in rows:
        m = await _pinned(c)
        if may_see_case(caller, m, c.case_key):
            out.append((c, m))
    return out


async def _resolve_unchecked(capability_id: str, team_group: str | None) -> tuple[int, int | None, Manifest]:
    """The manifest a new run would use, before any caller check."""
    from helix import groups as team_groups

    version, m = await capabilities.active(capability_id)
    if team_group:
        group_version, _, m = await team_groups.active_group(capability_id, team_group)
        return version, group_version, m
    return version, None, m


async def _resolve(capability_id: str, team_group: str | None,
                   caller: Caller) -> tuple[int, int | None, Manifest]:
    """The manifest a new run uses: the active capability version, merged with
    the active version of the chosen group when the capability has groups."""
    from helix import groups as team_groups

    version, m = await capabilities.active(capability_id)
    group_version = None
    active = await team_groups.active_groups(capability_id)
    if active:
        if not team_group:
            raise CaseError(f"choose a group: {', '.join(cfg.group for _, cfg, _ in active)}")
        group_version, _, m = await team_groups.active_group(capability_id, team_group)
    elif team_group:
        raise CaseError(f"{capability_id} has no groups")
    if not capabilities.can_see(caller, m):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}"
                              + (f" / {team_group}" if team_group else ""))
    return version, group_version, m


def _new_case(case_id: str, root: str, attempt: int, capability_id: str, version: int,
              team_group: str | None, group_version: int | None, m: Manifest, key: dict,
              caller: Caller, rerun_of: str | None = None) -> Case:
    return Case(case_id=case_id, root_case_id=root, attempt=attempt, rerun_of=rerun_of,
                capability_id=capability_id, manifest_version=version,
                team_group=team_group, team_group_version=group_version,
                manifest=m.model_dump(by_alias=True), case_key=key,
                subject=render(m.case.subject or " · ".join("{" + k + "}" for k in m.case.key), key),
                scope={scope: key[field] for field, scope in m.case.scopes.items()},
                status="running", opened_by=caller.user_id, run_as=caller.as_dict(),
                due_at=deadlines.due_at(m, key, datetime.now(timezone.utc)))


async def _latest_attempt(s, root: str) -> Case | None:
    return (await s.execute(select(Case).where(
        (Case.root_case_id == root) | (Case.case_id == root))
        .order_by(Case.attempt.desc()).limit(1))).scalars().first()


async def open_case(capability_id: str, case_key: dict, caller: Caller,
                    team_group: str | None = None, late: bool = False) -> str:
    """Open a case and start its run. Opening a key that already has a case
    returns its latest attempt — unless this is a later notification (`late`)
    and the capability takes late items (`case.late_items: follow_up`): then a
    follow-up case linked to it reads the source again for what is new.
    A capability with groups runs every case under one group — its team's
    configuration — on the merged manifest."""
    version, group_version, m = await _resolve(capability_id, team_group, caller)
    await _not_switched_off(capability_id, team_group)
    key = _check_key(m, case_key, caller)
    root = case_id_for(capability_id, {**key, "__group": team_group} if team_group else key)
    async with get_session() as s:
        if (existing := await _latest_attempt(s, root)) is not None:
            if not (late and m.case.late_items == "follow_up"):
                return existing.case_id
            n = (await s.execute(select(func.count()).select_from(Case).where(
                Case.follow_up_of == root))).scalar_one() + 1
            follow = _new_case(f"{root}.f{n}", f"{root}.f{n}", 1, capability_id, version, team_group,
                               group_version, m, key, caller)
            follow.follow_up_of, follow.subject = root, f"{follow.subject} · late items {n}"
            s.add(follow)
            await s.commit()
            await runner.submit(follow.case_id, "open")
            return follow.case_id
        s.add(_new_case(root, root, 1, capability_id, version, team_group, group_version,
                        m, key, caller))
        try:
            await s.commit()
        except IntegrityError:  # opened concurrently by someone else
            return root
    await runner.submit(root, "open")
    return root


async def _not_switched_off(capability_id: str, team_group: str | None) -> None:
    from helix import controls
    try:
        await controls.check_open(capability_id, team_group)
    except controls.SwitchedOff as e:
        raise CaseError(str(e)) from e


RERUNNABLE = ("failed", "escalated", "stopped")
GATE_PREFIX = "paused_before_"


def gate_step(status: str) -> str | None:
    """The step a case waits before at a tollgate, or None."""
    return status[len(GATE_PREFIX):] if status.startswith(GATE_PREFIX) else None


def may_pass_gate(caller: Caller, m: Manifest, step: str) -> bool:
    return caller.has_any_role(m.gate(step).roles)


async def pass_gate(case_id: str, step: str, action: str, comment: str | None,
                    idempotency_key: str, caller: Caller) -> dict:
    """A person at a tollgate: `continue` lets the run go on to `step`; `stop`
    ends it there (it can be re-run as a new attempt). Recorded either way."""
    if action not in ("continue", "stop"):
        raise CaseError("a tollgate is passed with continue or stop")
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        if not may_see_case(caller, m, case.case_key) and not may_pass_gate(caller, m, step):
            raise LookupError(case_id)
        existing = (await s.execute(select(GateDecision).where(
            GateDecision.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return {"replayed": True, "status": case.status}
        if gate_step(case.status) != step:
            raise CaseError(f"case is {case.status}, not waiting at the tollgate before `{step}`")
        if not may_see_case(caller, m, case.case_key) or not may_pass_gate(caller, m, step):
            raise PermissionError(f"passing this tollgate needs one of: {', '.join(m.gate(step).roles)}")
        if action == "stop" and m.gate(step).stop_needs_comment and not (comment or "").strip():
            raise CaseError("say why you stop the run: a comment is required")
        earlier = (await s.execute(select(GateDecision).where(
            GateDecision.case_id == case_id, GateDecision.action == "continue")
            .order_by(GateDecision.decided_at))).scalars().all()
        passed = [g.step for g in earlier]
        notes = [{"step": g.step, "by": g.decided_by, "comment": g.comment} for g in earlier if g.comment]
        if action == "continue" and (comment or "").strip():
            notes.append({"step": step, "by": caller.user_id, "comment": comment.strip()})
        s.add(GateDecision(gate_id=uuid.uuid4().hex, case_id=case_id, step=step, action=action,
                           comment=(comment or "").strip() or None, decided_by=caller.user_id,
                           idempotency_key=idempotency_key))
        if action == "stop":
            case.status, case.outcome = "stopped", "stopped"
            case.error = f"Stopped before `{step}` by {caller.user_id}: {(comment or '').strip()}"
        else:
            case.status = "running"
        await s.commit()
    with span("gate.decision", root=True, case_id=case_id, step=step, action=action, user=caller.user_id):
        if action == "continue":
            await runner.submit(case_id, "resume", {"gates_passed": [*passed, step], "gate_notes": notes})
        else:
            from helix import notify
            await notify.case_changed(case_id)
    async with get_session() as s:
        status = (await s.get(Case, case_id)).status
    return {"replayed": False, "status": status}


async def rerun_case(case_id: str, caller: Caller) -> str:
    """Run a failed or escalated case again, as a new attempt on today's
    active configuration. The earlier attempt stays as it was — it is evidence."""
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None or not may_see_case(caller, await _pinned(case), case.case_key):
            raise LookupError(case_id)
        root = case.root_case_id or case.case_id
        latest = await _latest_attempt(s, root)
        if latest.case_id != case_id:
            raise CaseError(f"a newer attempt exists: {latest.case_id}")
        if case.status not in RERUNNABLE:
            raise CaseError(f"case is {case.status}; only a failed, escalated or stopped case can be re-run")
    version, group_version, m = await _resolve(case.capability_id, case.team_group, caller)
    await _not_switched_off(case.capability_id, case.team_group)
    key = _check_key(m, case.case_key, caller)
    new_id = f"{root}.r{latest.attempt + 1}"
    async with get_session() as s:
        s.add(_new_case(new_id, root, latest.attempt + 1, case.capability_id, version,
                        case.team_group, group_version, m, key, caller, rerun_of=case_id))
        try:
            await s.commit()
        except IntegrityError as e:
            raise CaseError("this case is already being re-run") from e
    await runner.submit(new_id, "open")
    return new_id


async def follow_ups(case: Case) -> list[dict]:
    """The follow-up cases late items opened for this case's key."""
    root = case.follow_up_of or case.root_case_id or case.case_id
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(Case.follow_up_of == root)
                                .order_by(Case.opened_at))).scalars().all()
    return [{"case_id": c.case_id, "subject": c.subject, "status": c.status, "outcome": c.outcome,
             "opened_at": c.opened_at} for c in rows if c.case_id != case.case_id]


async def attempts(case: Case) -> list[dict]:
    root = case.root_case_id or case.case_id
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(
            (Case.root_case_id == root) | (Case.case_id == root))
            .order_by(Case.attempt))).scalars().all()
    return [{"case_id": r.case_id, "attempt": r.attempt, "status": r.status,
             "outcome": r.outcome, "opened_by": r.opened_by, "opened_at": r.opened_at} for r in rows]


def _group_env(m: Manifest, g: ProposalGroup, items: dict[str, dict]) -> dict:
    members = [items[i] for i in g.item_ids if i in items]
    amount = m.items.amount_field
    total = round(sum(float(it.get(amount) or 0) for it in members), 2) if amount else None
    return {**g.group_key, "total": total, "count": len(members), "label": g.label,
            "policy": m.policy_values()}


def _since_revision(g: ProposalGroup, decisions: list[Decision]) -> list[Decision]:
    """Decisions on the group's current finding — a re-investigation starts afresh."""
    revised = (g.finding or {}).get("revised_at")
    since = datetime.fromisoformat(revised) if revised else None
    return [d for d in decisions if d.group_id == g.group_id
            and (since is None or d.decided_at > since)]


def _settle(m: Manifest, g: ProposalGroup, decisions: list[Decision],
            items: dict[str, dict]) -> dict | None:
    """The group's outcome once its reviewers are done, else None.

    Each person's latest decision counts once. A reject from anyone rejects;
    otherwise it needs one approval, or two from different people when the
    capability's `review.dual_review_when` holds for the group."""
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
    needed = 2 if (m.review.dual_review_when and rules.evaluate(
        m.review.dual_review_when, _group_env(m, g, items))) else 1
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


async def _case_items(s, case_id: str) -> dict[str, dict]:
    rows = (await s.execute(select(CaseItem).where(CaseItem.case_id == case_id))).scalars().all()
    return {r.item_id: r.payload for r in rows}


async def decide(case_id: str, group_id: str, action: str, comment: str | None,
                 idempotency_key: str, caller: Caller, confirmed: bool = False,
                 review_seconds: int | None = None) -> dict:
    if action not in ("approve", "reject"):
        raise CaseError("action must be approve or reject")
    comment = (comment or "").strip() or None
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        existing = (await s.execute(select(Decision).where(
            Decision.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return {"decision_id": existing.decision_id, "replayed": True, "status": case.status}
        m = await _pinned(case)
        allowed, on_behalf_of = await review.acting_as(caller, m, case.case_key, may_see_case)
        if not allowed:
            raise PermissionError(f"{caller.user_id} may not decide on this case")
        if not m.review.opener_may_decide and case.opened_by in (caller.user_id, on_behalf_of):
            raise PermissionError("maker-checker: whoever opened the case cannot sign it off")
        if case.status != "awaiting_review":
            raise CaseError(f"case is {case.status}, not awaiting review")
        group = await s.get(ProposalGroup, (case_id, group_id))
        if group is None:
            raise CaseError(f"no group {group_id!r} in this case")
        if m.requests.hold_decision and (waiting := await asks.open_on_group(case_id, group_id)):
            raise CaseError(f"a question to {waiting[0].target_name} is still open; "
                            "wait for the answer or cancel the question")
        escalated = (group.finding or {}).get("status") == "escalated"
        if comment is None and action == "reject" and "reject" in m.review.require_comment:
            raise CaseError("say why you reject it: a comment is required")
        if comment is None and action == "approve" and escalated \
                and "escalated" in m.review.require_comment:
            raise CaseError("this group was escalated: approving it needs your explanation")
        if why := review.confirmation_problem(m, group.finding, action, confirmed, comment):
            raise CaseError(why)
        decision = Decision(decision_id=uuid.uuid4().hex, case_id=case_id, group_id=group_id,
                            action=action, comment=comment, decided_by=caller.user_id,
                            idempotency_key=idempotency_key,
                            confirmed=bool(confirmed and action == "approve"),
                            on_behalf_of=on_behalf_of,
                            review_seconds=(max(0, min(int(review_seconds), 8 * 3600))
                                            if review_seconds is not None else None))
        s.add(decision)
        await s.commit()

    with span("review.decision", root=True, case_id=case_id, group_id=group_id, action=action,
              user=caller.user_id):
        status = await _resume_if_complete(case_id, m)
    return {"decision_id": decision.decision_id, "replayed": False, "status": status}


async def bulk_decide(case_id: str, group_ids: list[str], action: str, comment: str | None,
                      idempotency_key: str, caller: Caller, review_seconds: int | None = None) -> dict:
    """The same decision on many groups. Each is checked on its own: an escalated
    group without a comment is refused while the others go through. Approving
    in bulk leaves the groups the capability marks for one-by-one review
    (review.bulk_exclude: e.g. a verdict needing confirmation, a judgement call)."""
    done, refused = [], []
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        findings = {g.group_id: g.finding for g in (await s.execute(select(ProposalGroup).where(
            ProposalGroup.case_id == case_id))).scalars()}
    for gid in dict.fromkeys(group_ids):
        if action == "approve" and (why := review.bulk_blockers(m, findings.get(gid))):
            refused.append({"group_id": gid, "reason": "needs one-by-one review: " + ", ".join(
                _FLAG_WORDS[f] for f in why)})
            continue
        try:
            share = round(review_seconds / max(1, len(group_ids))) if review_seconds is not None else None
            r = await decide(case_id, gid, action, comment, f"{idempotency_key}:{gid}", caller,
                             review_seconds=share)
            done.append({"group_id": gid, **r})
        except (CaseError, PermissionError) as e:
            refused.append({"group_id": gid, "reason": str(e)})
    async with get_session() as s:
        status = (await s.get(Case, case_id)).status
    return {"decided": done, "refused": refused, "status": status}


_pinned = runner.pinned

_FLAG_WORDS = {"confirmation": "the verdict needs your confirmation",
               "judgement": "a judgement call", "escalated": "escalated", "model": "proposed by the model"}


async def reinvestigate(case_id: str, group_id: str, note: str, idempotency_key: str,
                        caller: Caller) -> dict:
    """A reviewer sends one group back to the model with a note. The new
    finding goes through the same grounding check; decisions already taken on
    the group no longer count — it is reviewed afresh."""
    from helix import steps
    from helix.workflow import build_graph, checkpointer

    note = (note or "").strip()
    if not note:
        raise CaseError("say what to look at again: a note is required")
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        if not (await review.acting_as(caller, m, case.case_key, may_see_case))[0]:
            raise PermissionError(f"{caller.user_id} may not review this case")
        group = await s.get(ProposalGroup, (case_id, group_id))
        if group is None:
            raise CaseError(f"no group {group_id!r} in this case")
        previous = dict(group.finding or {})
        if idempotency_key in previous.get("reinvestigation_keys", []):
            return {"replayed": True, "status": case.status}
        if case.status != "awaiting_review":
            raise CaseError(f"case is {case.status}, not awaiting review")
        if m.reasoning.reasoner != "llm":
            raise CaseError("this capability has no model to investigate again")
        done = previous.get("reinvestigations", 0)
        if done >= m.review.max_reinvestigations:
            raise CaseError(f"this group was already sent back {done} time(s), the limit")
        case.status = "running"
        await s.commit()

    async def job():
        config = {"configurable": {"thread_id": f"helix:{case_id}"}}
        async with checkpointer() as cp:
            app = build_graph(m.steps, m.pause_before, cp)
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
            row = await s.get(ProposalGroup, (case_id, group_id))
            row.finding = finding
            c = await s.get(Case, case_id)
            if c.draft:
                c.draft = {**c.draft, "groups": [
                    {**x, "comment": finding.get("comment", "")} if x["group_id"] == group_id else x
                    for x in c.draft.get("groups", [])]}
            c.status = "awaiting_review"
            await s.commit()

    await runner.submit_job(case_id, job, "review.reinvestigate")
    async with get_session() as s:
        return {"replayed": False, "status": (await s.get(Case, case_id)).status}


def _latest(decisions: list[Decision]) -> dict[str, Decision]:
    out: dict[str, Decision] = {}
    for d in sorted(decisions, key=lambda d: d.decided_at):
        out[d.group_id] = d
    return out


async def _resume_if_complete(case_id: str, m: Manifest) -> str:
    """When every group is settled, hand the outcomes to the run and resume it."""
    async with get_session() as s:
        groups = (await s.execute(select(ProposalGroup).where(
            ProposalGroup.case_id == case_id))).scalars().all()
        decisions = (await s.execute(select(Decision).where(
            Decision.case_id == case_id))).scalars().all()
        items = await _case_items(s, case_id)
        settled = [_settle(m, g, decisions, items) for g in groups]
        case = await s.get(Case, case_id)
        if any(x is None for x in settled) or case.status != "awaiting_review":
            return case.status
        case.status = "running"
        await s.commit()
    await runner.submit(case_id, "resume", {"decisions": settled})
    async with get_session() as s:
        return (await s.get(Case, case_id)).status


async def approve_publish(case_id: str, idempotency_key: str, caller: Caller) -> dict:
    """A second person releases the write-back. Four-eyes: nobody who signed
    off a group in this case may release it."""
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        if not may_see_case(caller, m, case.case_key):
            raise LookupError(case_id)
        existing = await s.get(PublishApproval, case_id)
        if existing is not None:
            if existing.idempotency_key == idempotency_key:
                return {"replayed": True, "status": case.status}
            raise CaseError("write-back was already released")
        if m.publish is None or case.status != "awaiting_publish":
            raise CaseError(f"case is {case.status}, not awaiting publish")
        if not caller.has_any_role(m.publish.approver_roles):
            raise PermissionError(f"{caller.user_id} may not release write-back")
        if caller.user_id in await _deciders(s, case_id):
            raise PermissionError("four-eyes: a reviewer of this case cannot release its write-back")
        approval = PublishApproval(case_id=case_id, approved_by=caller.user_id,
                                   idempotency_key=idempotency_key)
        s.add(approval)
        case.status = "running"
        await s.commit()
    with span("publish.approval", root=True, case_id=case_id, user=caller.user_id):
        await runner.submit(case_id, "publish", {"publish_approval": {
            "approved_by": caller.user_id, "approved_at": runner.now_iso()}})
    async with get_session() as s:
        status = (await s.get(Case, case_id)).status
    return {"replayed": False, "status": status}


async def retry_publish(case_id: str, caller: Caller) -> dict:
    """Finish a write-back that failed part-way: only the writes that did not
    land are sent again, each with its original idempotency key. Same rules as
    the release — a publish approver who did not review the case."""
    from helix import steps
    from helix.workflow import build_graph, checkpointer

    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        if not may_see_case(caller, m, case.case_key):
            raise LookupError(case_id)
        if m.publish is None or case.outcome != "publish_failed":
            raise CaseError(f"case is {case.status}/{case.outcome}; nothing to retry")
        if not caller.has_any_role(m.publish.approver_roles):
            raise PermissionError(f"{caller.user_id} may not release write-back")
        if caller.user_id in await _deciders(s, case_id):
            raise PermissionError("four-eyes: a reviewer of this case cannot release its write-back")
        done = frozenset((await s.execute(select(ToolCall.idempotency_key).where(
            ToolCall.case_id == case_id, ToolCall.requested_by == "publish",
            ToolCall.allowed.is_(True), ToolCall.error.is_(None),
            ToolCall.idempotency_key.is_not(None)))).scalars())
        case.status = "running"
        await s.commit()

    async def job():
        config = {"configurable": {"thread_id": f"helix:{case_id}"}}
        async with checkpointer() as cp:
            state = (await build_graph(m.steps, m.pause_before, cp).aget_state(config)).values
        _, failed = await steps.write_back(state, caller.user_id, done)
        await steps.set_publish_outcome(case_id, failed)

    await runner.submit_job(case_id, job, "publish.retry")
    async with get_session() as s:
        c = await s.get(Case, case_id)
        return {"status": c.status, "outcome": c.outcome, "skipped": sorted(done)}


async def _deciders(s, case_id: str) -> set[str]:
    return set((await s.execute(select(Decision.decided_by).where(
        Decision.case_id == case_id))).scalars())


# ---------- reads ----------

def _case_summary(c: Case) -> dict:
    return {"case_id": c.case_id, "capability_id": c.capability_id, "subject": c.subject,
            "case_key": c.case_key, "status": c.status, "outcome": c.outcome,
            "manifest_version": c.manifest_version, "team_group": c.team_group,
            "team_group_version": c.team_group_version, "opened_by": c.opened_by,
            "opened_at": c.opened_at, "trace_id": c.trace_id, "error": c.error,
            "attempt": c.attempt or 1, "rerun_of": c.rerun_of, "legal_hold": bool(c.legal_hold),
            "due_at": c.due_at, "review_ready_at": c.review_ready_at,
            "follow_up_of": c.follow_up_of}


async def list_cases(capability_id: str, caller: Caller, team_group: str | None = None,
                     limit: int = 200, offset: int = 0) -> list[dict]:
    from helix import groups as team_groups

    _, m = await capabilities.active(capability_id)
    if not await team_groups.visible(caller, capability_id, m):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}")
    return [_case_summary(c) for c, _ in await visible_cases(
        caller, capability_id=capability_id, team_group=team_group, limit=limit, offset=offset)]


def _documents(case_id: str, calls: list[ToolCall]) -> list[dict]:
    """Reports this case's publish step wrote (a write tool's receipt that names a document)."""
    out = []
    for c in calls:
        r = c.result if isinstance(c.result, dict) else {}
        if c.requested_by == "publish" and c.allowed and not c.error and r.get("document"):
            out.append({"name": r["document"], "tool": c.tool, "pages": r.get("pages"),
                        "bytes": r.get("bytes"), "sha256": r.get("sha256"),
                        "written_at": c.called_at,
                        "url": f"/api/cases/{case_id}/documents/{r['document']}"})
    return out


async def _evidence(case_id: str) -> list[dict]:
    from helix import evidence
    return await evidence.for_case(case_id)


async def published_document(case_id: str, name: str, caller: Caller) -> tuple[str, str]:
    """(scope, name) of a report this case published, if the caller may see the case."""
    detail = await case_detail(case_id, caller)          # LookupError if not visible
    for c in detail["tool_calls"]:
        r = c["result"] if isinstance(c["result"], dict) else {}
        if c["requested_by"] == "publish" and c["allowed"] and r.get("document") == name:
            return r["scope"], name
    raise LookupError(f"{case_id}/{name}")


async def case_detail(case_id: str, caller: Caller) -> dict:
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        may_decide, on_behalf_of = await review.acting_as(caller, m, case.case_key, may_see_case)
        if not may_see_case(caller, m, case.case_key) and not may_decide:
            # Same answer as a missing case: a caller cannot tell the difference.
            raise LookupError(case_id)
        items = (await s.execute(select(CaseItem).where(CaseItem.case_id == case_id)
                                 .order_by(CaseItem.item_id))).scalars().all()
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.case_id == case_id)
                                  .order_by(ProposalGroup.group_id))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.case_id == case_id)
                                     .order_by(Decision.decided_at))).scalars().all()
        calls = (await s.execute(select(ToolCall).where(ToolCall.case_id == case_id)
                                 .order_by(ToolCall.called_at))).scalars().all()
        release = await s.get(PublishApproval, case_id)
        gates = (await s.execute(select(GateDecision).where(GateDecision.case_id == case_id)
                                 .order_by(GateDecision.decided_at))).scalars().all()
    latest = _latest(decisions)
    in_group = {i for g in groups for i in g.item_ids}
    tickets = await escalation.for_case(case_id)
    from helix import insights
    recurring = await insights.recurring_for_case(case, m, sorted(in_group))
    now = datetime.now(timezone.utc)
    return {
        **_case_summary(case),
        "due_state": deadlines.state(case.due_at, case.status, now,
                                     m.case.due.warn_hours if m.case.due else 2),
        "exposure": (case.draft or {}).get("exposure"), "unit": m.items.amount_unit,
        "id_field": m.items.id_field, "amount_field": m.items.amount_field,
        "recurring": recurring,
        "attempts": await attempts(case),
        "follow_ups": await follow_ups(case),
        # What became of this case's decisions in the next run (follow_through).
        "follow_through": (await follow_through.for_case(case_id)) if m.follow_through else None,
        "follow_through_spec": m.follow_through.model_dump() if m.follow_through else None,
        "requests": await asks.for_case(case_id, caller),
        "request_targets": [{"id": t.id, "name": t.name} for t in m.requests.targets],
        "can_ask": bool(m.requests.targets) and (
            (may_decide and case.status == "awaiting_review")
            or bool((st := gate_step(case.status)) and may_pass_gate(caller, m, st))),
        "draft": case.draft,
        "labels": {"case": m.case.label, "item": m.case.item_label},
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
            "decision": ({"action": latest[g.group_id].action,
                          "comment": latest[g.group_id].comment,
                          "decided_by": latest[g.group_id].decided_by,
                          "on_behalf_of": latest[g.group_id].on_behalf_of,
                          "confirmed": latest[g.group_id].confirmed,
                          "decided_at": latest[g.group_id].decided_at}
                         if g.group_id in latest else None),
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
                        "result": c.result} for c in calls],
        "documents": _documents(case_id, calls),
        "evidence": await _evidence(case_id),
        "can_decide": (may_decide and case.status == "awaiting_review"
                       and (m.review.opener_may_decide
                            or case.opened_by not in (caller.user_id, on_behalf_of))),
        "acting_for": on_behalf_of,
        "can_rerun": case.status in RERUNNABLE and capabilities.can_see(caller, m),
        "can_hold": capabilities.is_owner(caller, m),
        "legal_hold_reason": case.legal_hold_reason,
        "can_retry_publish": (case.outcome == "publish_failed" and m.publish is not None
                              and caller.has_any_role(m.publish.approver_roles)
                              and caller.user_id not in {d.decided_by for d in decisions}),
        "review": {"require_comment": m.review.require_comment,
                   "opener_may_decide": m.review.opener_may_decide,
                   "dual_review_when": m.review.dual_review_when,
                   "max_reinvestigations": m.review.max_reinvestigations,
                   "roles": list(m.review.roles),
                   "bulk_exclude": m.review.bulk_exclude, "confirm": m.review.confirm,
                   "allow_delegation": m.review.allow_delegation},
        "publish": ({"tool": m.publish.tool, "approver_roles": m.publish.approver_roles,
                     "per": m.publish.per,
                     "can_release": (case.status == "awaiting_publish"
                                     and caller.has_any_role(m.publish.approver_roles)
                                     and caller.user_id not in {d.decided_by for d in decisions}),
                     "released": ({"by": release.approved_by, "at": release.approved_at} if release else None)}
                    if m.publish else None),
        # Who the case waits on, and — when it is not this caller — why not, in plain words.
        "waiting_on": _waiting_on(case, m, caller, decisions, may_decide, on_behalf_of),
        "tollgates": [{"step": st, "roles": m.gate(st).roles, "check": m.gate(st).check}
                      for st in m.pause_before if st not in ("review", "publish")],
        "gate_decisions": [{"step": g.step, "action": g.action, "comment": g.comment,
                            "decided_by": g.decided_by, "decided_at": g.decided_at} for g in gates],
    }


def _waiting_on(case: Case, m: Manifest, caller: Caller, decisions: list[Decision],
                may_decide: bool, on_behalf_of: str | None) -> dict | None:
    deciders = {d.decided_by for d in decisions}
    if step := gate_step(case.status):
        gate = m.gate(step)
        why_not = None if may_pass_gate(caller, m, step) else f"passing this tollgate needs one of: {', '.join(gate.roles)}"
        return {"step": "gate", "gate": step, "roles": list(gate.roles), "check": gate.check,
                "stop_needs_comment": gate.stop_needs_comment, "you": why_not is None, "why_not": why_not}
    if case.status == "awaiting_review":
        why_not = None
        if not may_decide:
            why_not = f"reviewing needs one of: {', '.join(m.review.roles)}"
        elif not m.review.opener_may_decide and case.opened_by in (caller.user_id, on_behalf_of):
            why_not = "you opened this case, and its capability needs someone else to sign it off"
        return {"step": "review", "roles": list(m.review.roles), "you": why_not is None, "why_not": why_not}
    if case.status == "awaiting_publish" and m.publish:
        why_not = None
        if not caller.has_any_role(m.publish.approver_roles):
            why_not = f"releasing needs one of: {', '.join(m.publish.approver_roles)}"
        elif caller.user_id in deciders:
            why_not = "you reviewed this case; a second person who did not review it releases it"
        return {"step": "release", "roles": list(m.publish.approver_roles), "you": why_not is None,
                "why_not": why_not, "reviewed_by": sorted(deciders)}
    return None
