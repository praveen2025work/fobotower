"""Cross-capability reads for the unified console: overview, inbox, audit.

Everything is filtered exactly as the per-case reads are — a caller sees a
capability only with one of its roles, and a case only within their data
scope — so these views never reveal a case `case_detail` would hide.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from helix import capabilities
from helix.cases import may_see_case
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import (
    Case,
    CapabilityVersion,
    Decision,
    ProposalGroup,
    PublishApproval,
    ToolCall,
)


async def _visible_cases(caller: Caller) -> list[tuple[Case, Manifest]]:
    async with get_session() as s:
        versions = {(v.capability_id, v.version): Manifest.model_validate(v.manifest)
                    for v in (await s.execute(select(CapabilityVersion))).scalars()}
        rows = (await s.execute(select(Case).order_by(Case.opened_at.desc()))).scalars().all()
    out = []
    for c in rows:
        m = Manifest.model_validate(c.manifest) if c.manifest else versions.get(
            (c.capability_id, c.manifest_version))
        if m and may_see_case(caller, m, c.case_key):
            out.append((c, m))
    return out


async def _groups_by_case(case_ids: list[str]) -> dict[str, list[ProposalGroup]]:
    if not case_ids:
        return {}
    async with get_session() as s:
        rows = (await s.execute(select(ProposalGroup).where(
            ProposalGroup.case_id.in_(case_ids)))).scalars().all()
    out: dict[str, list[ProposalGroup]] = defaultdict(list)
    for g in rows:
        out[g.case_id].append(g)
    return out


async def _decisions_by_case(case_ids: list[str]) -> dict[str, list[Decision]]:
    if not case_ids:
        return {}
    async with get_session() as s:
        rows = (await s.execute(select(Decision).where(Decision.case_id.in_(case_ids)))).scalars().all()
    out: dict[str, list[Decision]] = defaultdict(list)
    for d in rows:
        out[d.case_id].append(d)
    return out


def _summary(c: Case, m: Manifest, groups: list[ProposalGroup], decided: set[str]) -> dict:
    statuses = Counter((g.finding or {}).get("status", "pending") for g in groups)
    return {
        "case_id": c.case_id, "capability_id": c.capability_id, "capability_name": m.name,
        "case_label": m.case.label, "subject": c.subject, "status": c.status,
        "team_group": c.team_group,
        "outcome": c.outcome, "opened_at": c.opened_at, "opened_by": c.opened_by,
        "groups": len(groups), "proposed": statuses.get("proposed", 0),
        "escalated": statuses.get("escalated", 0),
        "decided": len({g.group_id for g in groups} & decided),
    }


def _my_action(c: Case, m: Manifest, caller: Caller, deciders: set[str]) -> str | None:
    if c.status == "awaiting_review" and caller.has_any_role(m.review.roles):
        return "review"
    if (c.status == "awaiting_publish" and m.publish
            and caller.has_any_role(m.publish.approver_roles) and caller.user_id not in deciders):
        return "release"
    return None


async def inbox(caller: Caller) -> list[dict]:
    """Every case waiting on this caller, across capabilities, oldest first."""
    visible = await _visible_cases(caller)
    ids = [c.case_id for c, _ in visible]
    groups, decisions = await _groups_by_case(ids), await _decisions_by_case(ids)
    out = []
    for c, m in visible:
        deciders = {d.decided_by for d in decisions.get(c.case_id, [])}
        action = _my_action(c, m, caller, deciders)
        if action:
            decided = {d.group_id for d in decisions.get(c.case_id, [])}
            out.append({**_summary(c, m, groups.get(c.case_id, []), decided), "action": action})
    return sorted(out, key=lambda r: r["opened_at"])


async def overview(caller: Caller) -> dict:
    visible = await _visible_cases(caller)
    ids = [c.case_id for c, _ in visible]
    groups, decisions = await _groups_by_case(ids), await _decisions_by_case(ids)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    async with get_session() as s:
        calls = (await s.execute(select(ToolCall).where(
            ToolCall.called_at >= since, ToolCall.case_id.in_(ids or [""])))).scalars().all()

    per_cap: dict[str, dict] = {}
    from helix import groups as team_groups

    for _, m in await capabilities.all_active():
        if await team_groups.visible(caller, m.id, m):
            per_cap[m.id] = {"id": m.id, "name": m.name, "case_label": m.case.label,
                             "statuses": Counter(), "escalated_groups": 0}
    mine = Counter()
    llm_cost, llm_groups = 0.0, 0
    for c, m in visible:
        cap = per_cap.setdefault(m.id, {"id": m.id, "name": m.name, "case_label": m.case.label,
                                        "statuses": Counter(), "escalated_groups": 0})
        cap["statuses"][c.status] += 1
        gs = groups.get(c.case_id, [])
        cap["escalated_groups"] += sum(1 for g in gs if (g.finding or {}).get("status") == "escalated")
        for g in gs:
            usage = (g.finding or {}).get("usage") or {}
            if usage.get("cost_usd") is not None:
                llm_cost += usage["cost_usd"]
                llm_groups += 1
        action = _my_action(c, m, caller, {d.decided_by for d in decisions.get(c.case_id, [])})
        if action:
            mine[action] += 1
    return {
        "awaiting_my_review": mine["review"],
        "awaiting_my_release": mine["release"],
        "open_cases": sum(1 for c, _ in visible if c.status not in ("completed", "failed", "escalated")),
        "escalated_groups": sum(v["escalated_groups"] for v in per_cap.values()),
        "tool_calls_24h": len(calls),
        "refused_calls_24h": sum(1 for t in calls if not t.allowed),
        "model_calls_24h": sum(1 for t in calls if t.requested_by == "llm"),
        "llm_cost_usd": round(llm_cost, 4), "llm_groups": llm_groups,
        "capabilities": [{**v, "statuses": dict(v["statuses"])} for v in per_cap.values()],
    }


async def audit(caller: Caller, *, capability_id: str | None = None, limit: int = 200) -> list[dict]:
    """Newest-first events a caller may see: connector calls, sign-offs, releases."""
    visible = {c.case_id: (c, m) for c, m in await _visible_cases(caller)
               if capability_id in (None, c.capability_id)}
    ids = list(visible) or [""]
    async with get_session() as s:
        calls = (await s.execute(select(ToolCall).where(ToolCall.case_id.in_(ids))
                                 .order_by(ToolCall.called_at.desc()).limit(limit))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.case_id.in_(ids))
                                     .order_by(Decision.decided_at.desc()).limit(limit))).scalars().all()
        releases = (await s.execute(select(PublishApproval).where(PublishApproval.case_id.in_(ids))
                                    )).scalars().all()
    events = []
    for t in calls:
        c, _ = visible[t.case_id]
        events.append({
            "kind": "tool_call", "at": t.called_at, "case_id": t.case_id, "subject": c.subject,
            "capability_id": c.capability_id, "actor": t.caller, "requested_by": t.requested_by,
            "tool": t.tool, "allowed": t.allowed, "detail": t.denied_reason or t.error,
            "row_count": t.row_count, "latency_ms": t.latency_ms,
        })
    for d in decisions:
        c, _ = visible[d.case_id]
        events.append({"kind": "decision", "at": d.decided_at, "case_id": d.case_id,
                       "subject": c.subject, "capability_id": c.capability_id,
                       "actor": d.decided_by, "action": d.action, "group_id": d.group_id,
                       "detail": d.comment})
    for r in releases:
        c, _ = visible[r.case_id]
        events.append({"kind": "release", "at": r.approved_at, "case_id": r.case_id,
                       "subject": c.subject, "capability_id": c.capability_id,
                       "actor": r.approved_by, "detail": "write-back released"})
    return sorted(events, key=lambda e: e["at"], reverse=True)[:limit]
