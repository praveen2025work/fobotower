"""Cross-capability reads for the unified console: overview, inbox, audit.

Everything is filtered exactly as the per-case reads are — a caller sees a
capability only with one of its roles, and a case only within their data
scope — so these views never reveal a case `case_detail` would hide.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from helix import capabilities
from helix.cases import visible_cases
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import (
    Case,
    CapabilityVersion,
    Decision,
    Document,
    ProposalGroup,
    PublishApproval,
    ToolCall,
)


async def _visible_cases(caller: Caller, **filters) -> list[tuple[Case, Manifest]]:
    return await visible_cases(caller, **filters)


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
    visible = await _visible_cases(caller, statuses=("awaiting_review", "awaiting_publish"))
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
    month = datetime.now(timezone.utc) - timedelta(days=30)
    saved = {"items": 0, "groups": 0, "minutes": 0.0, "settled": 0}
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
        if c.opened_at >= month and gs:
            # FOBO's efficiency claim: items that would each have been a decision,
            # against the groups they collapsed into, at a declared manual cost.
            n_items = sum(len(g.item_ids) for g in gs)
            saved["items"] += n_items
            saved["groups"] += len(gs)
            saved["minutes"] += (n_items - len(gs)) * m.metrics.manual_minutes_per_item
            saved["settled"] += sum(1 for g in gs if (g.finding or {}).get("decided_by") in ("rule", "playbook"))
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
        "model_calls_24h": sum(1 for t in calls if t.requested_by in ("llm", "chat")),
        "llm_cost_usd": round(llm_cost, 4), "llm_groups": llm_groups,
        "hours_saved_30d": {
            "value": round(saved["minutes"] / 60, 1),
            "basis": (f"{saved['items']} items grouped into {saved['groups']} decisions "
                      f"({saved['items'] - saved['groups']} avoided) at each capability's declared "
                      f"manual minutes per item; {saved['settled']} groups settled by rule or playbook"),
        },
        "capabilities": [{**v, "statuses": dict(v["statuses"])} for v in per_cap.values()],
    }


async def audit(caller: Caller, *, capability_id: str | None = None, limit: int = 200) -> list[dict]:
    """Newest-first events a caller may see: connector calls, sign-offs, releases."""
    # the newest cases' events; older ones are a capability filter away
    visible = {c.case_id: (c, m) for c, m in await _visible_cases(
        caller, capability_id=capability_id, limit=2000)}
    ids = list(visible) or [""]
    async with get_session() as s:
        calls = (await s.execute(select(ToolCall).where(ToolCall.case_id.in_(ids))
                                 .order_by(ToolCall.called_at.desc()).limit(limit))).scalars().all()
        decisions = (await s.execute(select(Decision).where(Decision.case_id.in_(ids))
                                     .order_by(Decision.decided_at.desc()).limit(limit))).scalars().all()
        releases = (await s.execute(select(PublishApproval).where(PublishApproval.case_id.in_(ids))
                                    )).scalars().all()
        uploads = (await s.execute(select(Document.case_id, Document.name, Document.uploaded_by,
                                          Document.created_at, Document.sha256).where(
            Document.case_id.in_(ids), Document.kind == "evidence"))).all()
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
    for u in uploads:
        c, _ = visible[u.case_id]
        events.append({"kind": "evidence", "at": u.created_at, "case_id": u.case_id,
                       "subject": c.subject, "capability_id": c.capability_id,
                       "actor": u.uploaded_by, "detail": f"uploaded {u.name} (sha256 {u.sha256[:12]}…)"})
    return sorted(events, key=lambda e: e["at"], reverse=True)[:limit]


# ---------- operations (run-the-bank) ----------

def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def _delta(now: float, before: float) -> float:
    return 0.0 if not before else round((now - before) / before * 100, 1)


async def _connector_health() -> list[dict]:
    import asyncio
    import time

    from helix import gateway

    async def probe(cid, spec) -> dict:
        started = time.monotonic()
        try:
            async with gateway._client(spec) as client:
                listed = await asyncio.wait_for(client.list_tools(), timeout=3)
            status, error, found = "up", None, len(listed.tools)
        except Exception as e:  # down, timeout, protocol error — reported, never raised
            status, error, found = "down", f"{type(e).__name__}: {e}"[:200], 0
        return {"id": cid, "name": spec.name, "transport": spec.transport,
                "classification": spec.classification, "status": status, "error": error,
                "tools_allowed": len(spec.tools), "tools_served": found,
                "latency_ms": int((time.monotonic() - started) * 1000)}

    reg = gateway.registry()
    return list(await asyncio.gather(*(probe(cid, spec) for cid, spec in reg.connectors.items())))


async def operations(caller: Caller) -> dict:
    """What run-the-bank support needs on one screen — aria-ai's Mission Control,
    on Helix data. Case-derived figures are scoped to what the caller may see."""
    from sqlalchemy import text as sql

    from helix.config import settings
    from helix.llm import llm

    now = datetime.now(timezone.utc)
    day, prev = now - timedelta(hours=24), now - timedelta(hours=48)
    visible = await _visible_cases(caller)
    ids = [c.case_id for c, _ in visible]
    groups = await _groups_by_case(ids)
    async with get_session() as s:
        db_ok = (await s.execute(sql("SELECT 1"))).scalar() == 1
        calls = (await s.execute(select(ToolCall).where(
            ToolCall.called_at >= prev, ToolCall.case_id.in_(ids or [""]))
            .order_by(ToolCall.called_at))).scalars().all()
        decisions = (await s.execute(select(Decision).where(
            Decision.decided_at >= day, Decision.case_id.in_(ids or [""])))).scalars().all()
    calls_now = [t for t in calls if t.called_at >= day]
    calls_before = [t for t in calls if t.called_at < day]

    def usage(case_ids) -> tuple[float, int]:
        cost, tokens = 0.0, 0
        for cid in case_ids:
            for g in groups.get(cid, []):
                u = (g.finding or {}).get("usage") or {}
                cost += u.get("cost_usd") or 0
                tokens += (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
        return round(cost, 4), tokens

    cases_now = [(c, m) for c, m in visible if c.opened_at >= day]
    cases_before = [(c, m) for c, m in visible if prev <= c.opened_at < day]
    failed = lambda rows: sum(1 for c, _ in rows if c.status == "failed")  # noqa: E731
    errors_now = failed(cases_now) + sum(1 for t in calls_now if t.error)
    errors_before = failed(cases_before) + sum(1 for t in calls_before if t.error)
    cost_now, _ = usage([c.case_id for c, _ in cases_now])
    cost_before, _ = usage([c.case_id for c, _ in cases_before])
    p95_now = _p95([(t.latency_ms or 0) / 1000 for t in calls_now if t.allowed])
    p95_before = _p95([(t.latency_ms or 0) / 1000 for t in calls_before if t.allowed])
    pending = sum(1 for c, _ in visible if c.status in ("awaiting_review", "awaiting_publish"))

    # One fleet row per capability × team group, in aria-ai's FleetAgent shape.
    from helix import groups as team_groups

    group_names: dict[tuple, str] = {}
    for cap_id in {c.capability_id for c, _ in visible}:
        for _, cfg, _ in await team_groups.active_groups(cap_id):
            group_names[(cap_id, cfg.group)] = cfg.name
    fleet: dict[tuple, dict] = {}
    for c, m in visible:
        key = (c.capability_id, c.team_group)
        row = fleet.setdefault(key, {
            "name": group_names.get(key, c.team_group) if c.team_group else m.name, "team": m.name,
            "env": c.team_group or "—", "status": "active", "runs24": 0, "errs24": 0,
            "p95": 0.0, "tokens24": 0, "cost24": 0.0, "sparkline": [1.0] * 24, "lastRunAt": None,
            "href": f"/capabilities/{c.capability_id}" + (f"/groups/{c.team_group}" if c.team_group else ""),
            "_hours": [[0, 0] for _ in range(24)], "_ids": []})
        row["_ids"].append(c.case_id)
        row["lastRunAt"] = max(filter(None, [row["lastRunAt"], c.opened_at.isoformat()]))
        if c.opened_at >= day:
            row["runs24"] += 1
            bad = c.status in ("failed", "escalated")
            row["errs24"] += int(bad)
            hour = min(23, int((now - c.opened_at).total_seconds() // 3600))
            row["_hours"][23 - hour][0] += 1
            row["_hours"][23 - hour][1] += int(not bad)
    for row in fleet.values():
        ids_ = set(row.pop("_ids"))
        row["cost24"], row["tokens24"] = usage(ids_)
        row["p95"] = round(_p95([(t.latency_ms or 0) / 1000 for t in calls_now
                                 if t.case_id in ids_ and t.allowed]), 3)
        row["sparkline"] = [ok / n if n else 1.0 for n, ok in row.pop("_hours")]
        escalated = any((g.finding or {}).get("status") == "escalated"
                        for cid in ids_ for g in groups.get(cid, []))
        row["status"] = "error" if row["errs24"] else "degraded" if escalated else "active"

    # Incidents: refusals and connector errors by tool, failed cases by capability.
    incidents: dict[tuple, dict] = {}
    def incident(key, title, affecting, at, status):  # noqa: E306
        inc = incidents.setdefault(key, {"id": "-".join(map(str, key)), "title": title,
                                         "affecting": affecting, "first": at, "count": 0,
                                         "status": status})
        inc["count"] += 1
        inc["first"] = min(inc["first"], at)
    for t in calls_now:
        if not t.allowed:
            incident(("refused", t.tool), f"Refused calls to {t.tool}", t.capability_id, t.called_at, "degraded")
        elif t.error:
            incident(("error", t.tool), f"Connector errors from {t.tool}", t.connector_id, t.called_at, "error")
    for c, m in cases_now:
        if c.status == "failed":
            incident(("failed", c.capability_id), "Failed case runs", m.name, c.opened_at, "error")
    incident_rows = [{**{k: v for k, v in i.items() if k != "first"},
                      "sinceMinutes": int((now - i["first"]).total_seconds() // 60)}
                     for i in incidents.values()]

    tail = [{"id": t.call_id, "ts": t.called_at.isoformat(),
             "level": "error" if t.error else "warn" if not t.allowed else "info",
             "source": t.requested_by,
             "message": f"{t.tool} {'refused: ' + (t.denied_reason or '') if not t.allowed else 'error: ' + t.error if t.error else f'{t.row_count if t.row_count is not None else 0} rows in {t.latency_ms} ms'}"}
            for t in calls_now[-60:]]
    tail += [{"id": f"d-{d.decision_id}", "ts": d.decided_at.isoformat(), "level": "info",
              "source": d.decided_by, "message": f"{d.action} {d.group_id} on {d.case_id}"}
             for d in decisions]
    tail.sort(key=lambda line: line["ts"])

    tracing = ("phoenix" if settings().phoenix_endpoint else
               "custom" if settings().tracing_setup else "off")
    return {
        "health": {"status": "healthy" if db_ok else "degraded", "database": "connected" if db_ok else "down",
                   "llm": llm().name, "tracing": tracing,
                   "entitlement": "central" if settings().entitlement_url else "dev-stub"},
        "connectors": await _connector_health(),
        "kpi": {"cost24": cost_now, "cost24Delta": _delta(cost_now, cost_before),
                "runs24": len(cases_now), "runs24Delta": _delta(len(cases_now), len(cases_before)),
                "p95": round(p95_now, 3), "p95Delta": _delta(p95_now, p95_before),
                "pendingApprovals": pending, "pendingDelta": 0.0,
                "errors24": errors_now, "errors24Delta": _delta(errors_now, errors_before)},
        "fleet": sorted(fleet.values(), key=lambda r: (r["team"], r["name"])),
        "incidents": sorted(incident_rows, key=lambda i: i["sinceMinutes"]),
        "tail": tail[-80:],
    }
