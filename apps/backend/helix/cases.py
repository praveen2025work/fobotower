"""Cases: open one, run it to the review pause, take decisions, resume to record.

A case is identified by its capability and key (e.g. entity + period), so
opening the same key twice returns the existing case rather than running it
again. The run is pinned to the manifest version active when it opened and
to the caller's entitlements at that moment.
"""

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from helix import capabilities
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import Case, CaseItem, Decision, ProposalGroup, PublishApproval, ToolCall
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
        elif "publish" in snapshot.next:
            case.status = "awaiting_publish"
        elif snapshot.next:
            case.status = f"paused_before_{snapshot.next[0]}"
        await s.commit()
        return case.status


async def open_case(capability_id: str, case_key: dict, caller: Caller,
                    team_group: str | None = None) -> str:
    """Open (and run) a case. A capability with groups runs every case under one
    group — its team's configuration — on the merged manifest."""
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
    key = _check_key(m, case_key, caller)
    case_id = case_id_for(capability_id, {**key, "__group": team_group} if team_group else key)
    async with get_session() as s:
        if await s.get(Case, case_id) is not None:
            return case_id
        s.add(Case(case_id=case_id, capability_id=capability_id, manifest_version=version,
                   team_group=team_group, team_group_version=group_version,
                   manifest=m.model_dump(by_alias=True),
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
    """The exact manifest the case ran on: its snapshot (capability + group),
    or for older cases the capability version it opened with."""
    if case.manifest:
        return Manifest.model_validate(case.manifest)
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
                "decided_by": d.decided_by, "decided_at": d.decided_at.isoformat()}
               for d in decisions.values()]
    try:
        async with checkpointer() as cp:
            app = build_graph(m.steps, m.pause_before, cp)
            await app.aupdate_state(config, {"decisions": payload})
            await app.ainvoke(None, config)
            return await _status_after_run(app, config, case_id)
    except Exception as e:
        await _fail(case_id, e)
        raise


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
        deciders = set((await s.execute(select(Decision.decided_by).where(
            Decision.case_id == case_id))).scalars())
        if caller.user_id in deciders:
            raise PermissionError("four-eyes: a reviewer of this case cannot release its write-back")
        s.add(PublishApproval(case_id=case_id, approved_by=caller.user_id,
                              idempotency_key=idempotency_key))
        await s.commit()

    config = {"configurable": {"thread_id": f"helix:{case_id}"}}
    with span("publish.approval", root=True, case_id=case_id, user=caller.user_id):
        try:
            async with checkpointer() as cp:
                app = build_graph(m.steps, m.pause_before, cp)
                await app.aupdate_state(config, {"publish_approval": {
                    "approved_by": caller.user_id,
                    "approved_at": datetime.now(timezone.utc).isoformat()}})
                await app.ainvoke(None, config)
                status = await _status_after_run(app, config, case_id)
        except Exception as e:
            await _fail(case_id, e)
            raise
    async with get_session() as s:
        status = (await s.get(Case, case_id)).status
    return {"replayed": False, "status": status}


# ---------- reads ----------

def _case_summary(c: Case) -> dict:
    return {"case_id": c.case_id, "capability_id": c.capability_id, "subject": c.subject,
            "case_key": c.case_key, "status": c.status, "outcome": c.outcome,
            "manifest_version": c.manifest_version, "team_group": c.team_group,
            "team_group_version": c.team_group_version, "opened_by": c.opened_by,
            "opened_at": c.opened_at, "trace_id": c.trace_id, "error": c.error}


async def list_cases(capability_id: str, caller: Caller, team_group: str | None = None) -> list[dict]:
    from helix import groups as team_groups

    _, m = await capabilities.active(capability_id)
    if not await team_groups.visible(caller, capability_id, m):
        raise PermissionError(f"{caller.user_id} has no role for {capability_id}")
    query = select(Case).where(Case.capability_id == capability_id)
    if team_group:
        query = query.where(Case.team_group == team_group)
    async with get_session() as s:
        rows = (await s.execute(query.order_by(Case.opened_at.desc()))).scalars().all()
    out = []
    for c in rows:
        if may_see_case(caller, await _pinned(c), c.case_key):
            out.append(_case_summary(c))
    return out


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
        "steps": m.steps, "pause_before": m.pause_before,
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
        "documents": _documents(case_id, calls),
        "can_decide": caller.has_any_role(m.review.roles) and case.status == "awaiting_review",
        "publish": ({"tool": m.publish.tool, "approver_roles": m.publish.approver_roles,
                     "can_release": (case.status == "awaiting_publish"
                                     and caller.has_any_role(m.publish.approver_roles)
                                     and caller.user_id not in {d.decided_by for d in decisions})}
                    if m.publish else None),
    }
