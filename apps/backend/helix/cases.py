"""Cases: open one, run it to the review pause, take decisions, resume to record.

A case is identified by its capability and key (e.g. entity + period), so
opening the same key twice returns the existing case rather than running it
again. The run is pinned to the manifest version active when it opened and
to the caller's entitlements at that moment.
"""

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from helix import capabilities
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import Case, CaseItem, Decision, ProposalGroup, ToolCall
from helix.observability import current_trace_id, span
from helix.rules import render
from helix.workflow import build_graph, checkpointer


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


async def _status_after_run(app, config, case_id: str) -> str:
    snapshot = await app.aget_state(config)
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if "review" in snapshot.next:
            case.status = "awaiting_review"
        elif snapshot.next:
            case.status = f"paused_before_{snapshot.next[0]}"
        await s.commit()
        return case.status


async def open_case(capability_id: str, case_key: dict, caller: Caller) -> str:
    version, m = await capabilities.active(capability_id)
    if not capabilities.can_see(caller, m):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}")
    key = _check_key(m, case_key, caller)
    case_id = case_id_for(capability_id, key)
    async with get_session() as s:
        if await s.get(Case, case_id) is not None:
            return case_id
        s.add(Case(case_id=case_id, capability_id=capability_id, manifest_version=version,
                   case_key=key, subject=render(m.case.subject or " · ".join(
                       "{" + k + "}" for k in m.case.key), key),
                   status="running", opened_by=caller.user_id))
        try:
            await s.commit()
        except IntegrityError:  # opened concurrently by someone else
            return case_id

    state = {"case_id": case_id, "capability_id": capability_id, "manifest_version": version,
             "manifest": m.model_dump(by_alias=True), "case_key": key,
             "caller": caller.as_dict()}
    config = {"configurable": {"thread_id": f"helix:{case_id}"}}
    with span("case.run", root=True, input=key, case_id=case_id, capability_id=capability_id,
              manifest_version=version, user=caller.user_id):
        trace_id = current_trace_id()
        try:
            async with checkpointer() as cp:
                app = build_graph(m.steps, m.pause_before, cp)
                await app.ainvoke(state, config)
                await _status_after_run(app, config, case_id)
        except Exception as e:
            await _fail(case_id, e)
            raise
    if trace_id:
        async with get_session() as s:
            (await s.get(Case, case_id)).trace_id = trace_id
            await s.commit()
    return case_id


async def _fail(case_id: str, e: Exception) -> None:
    async with get_session() as s:
        case = await s.get(Case, case_id)
        case.status, case.error = "failed", f"{type(e).__name__}: {e}"
        await s.commit()


async def decide(case_id: str, group_id: str, action: str, comment: str | None,
                 idempotency_key: str, caller: Caller) -> dict:
    if action not in ("approve", "reject"):
        raise CaseError("action must be approve or reject")
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        existing = (await s.execute(select(Decision).where(
            Decision.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing is not None:
            return {"decision_id": existing.decision_id, "replayed": True, "status": case.status}
        m = await _pinned(case)
        if not may_see_case(caller, m, case.case_key) or not caller.has_any_role(m.review.roles):
            raise PermissionError(f"{caller.user_id} may not decide on this case")
        if case.status != "awaiting_review":
            raise CaseError(f"case is {case.status}, not awaiting review")
        if await s.get(ProposalGroup, (case_id, group_id)) is None:
            raise CaseError(f"no group {group_id!r} in this case")
        decision = Decision(decision_id=uuid.uuid4().hex, case_id=case_id, group_id=group_id,
                            action=action, comment=comment, decided_by=caller.user_id,
                            idempotency_key=idempotency_key)
        s.add(decision)
        await s.commit()

    with span("review.decision", root=True, case_id=case_id, group_id=group_id, action=action,
              user=caller.user_id):
        status = await _resume_if_complete(case_id, m)
    return {"decision_id": decision.decision_id, "replayed": False, "status": status}


async def _pinned(case: Case) -> Manifest:
    from helix.models import CapabilityVersion
    async with get_session() as s:
        row = await s.get(CapabilityVersion, (case.capability_id, case.manifest_version))
    return Manifest.model_validate(row.manifest)


def _latest(decisions: list[Decision]) -> dict[str, Decision]:
    out: dict[str, Decision] = {}
    for d in sorted(decisions, key=lambda d: d.decided_at):
        out[d.group_id] = d
    return out


async def _resume_if_complete(case_id: str, m: Manifest) -> str:
    async with get_session() as s:
        groups = (await s.execute(select(ProposalGroup.group_id).where(
            ProposalGroup.case_id == case_id))).scalars().all()
        decisions = _latest((await s.execute(select(Decision).where(
            Decision.case_id == case_id))).scalars().all())
        case = await s.get(Case, case_id)
        if set(groups) - set(decisions):
            return case.status
    config = {"configurable": {"thread_id": f"helix:{case_id}"}}
    payload = [{"group_id": d.group_id, "action": d.action, "comment": d.comment,
                "decided_by": d.decided_by} for d in decisions.values()]
    try:
        async with checkpointer() as cp:
            app = build_graph(m.steps, m.pause_before, cp)
            await app.aupdate_state(config, {"decisions": payload})
            await app.ainvoke(None, config)
            return await _status_after_run(app, config, case_id)
    except Exception as e:
        await _fail(case_id, e)
        raise


# ---------- reads ----------

def _case_summary(c: Case) -> dict:
    return {"case_id": c.case_id, "capability_id": c.capability_id, "subject": c.subject,
            "case_key": c.case_key, "status": c.status, "outcome": c.outcome,
            "manifest_version": c.manifest_version, "opened_by": c.opened_by,
            "opened_at": c.opened_at, "trace_id": c.trace_id, "error": c.error}


async def list_cases(capability_id: str, caller: Caller) -> list[dict]:
    _, m = await capabilities.active(capability_id)
    if not capabilities.can_see(caller, m):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}")
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(Case.capability_id == capability_id)
                                .order_by(Case.opened_at.desc()))).scalars().all()
    return [_case_summary(c) for c in rows if may_see_case(caller, m, c.case_key)]


async def case_detail(case_id: str, caller: Caller) -> dict:
    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        if not may_see_case(caller, m, case.case_key):
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
    latest = _latest(decisions)
    in_group = {i for g in groups for i in g.item_ids}
    return {
        **_case_summary(case),
        "draft": case.draft,
        "labels": {"case": m.case.label, "item": m.case.item_label},
        "columns": m.items.display or sorted({k for it in items for k in it.payload}),
        "items": [{"item_id": it.item_id, "in_scope": it.item_id in in_group, **it.payload}
                  for it in items],
        "groups": [{
            "group_id": g.group_id, "label": g.label, "group_key": g.group_key,
            "item_ids": g.item_ids, "priors": g.priors, "finding": g.finding,
            "decision": ({"action": latest[g.group_id].action,
                          "comment": latest[g.group_id].comment,
                          "decided_by": latest[g.group_id].decided_by,
                          "decided_at": latest[g.group_id].decided_at}
                         if g.group_id in latest else None),
        } for g in groups],
        "decisions": [{"group_id": d.group_id, "action": d.action, "comment": d.comment,
                       "decided_by": d.decided_by, "decided_at": d.decided_at}
                      for d in decisions],
        "tool_calls": [{"call_id": c.call_id, "tool": c.tool, "connector_id": c.connector_id,
                        "requested_by": c.requested_by, "caller": c.caller,
                        "arguments": c.arguments, "allowed": c.allowed,
                        "denied_reason": c.denied_reason, "row_count": c.row_count,
                        "error": c.error, "latency_ms": c.latency_ms, "called_at": c.called_at,
                        "result": c.result} for c in calls],
        "can_decide": caller.has_any_role(m.review.roles) and case.status == "awaiting_review",
    }
