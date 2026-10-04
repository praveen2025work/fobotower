"""Run-the-bank controls: off switches and spend limits.

Off switches — a capability, one team's group, or a connector:
  * a capability or group that is off opens no case (people, schedules, events);
  * the gateway refuses every call for a capability that is off, and every
    call to a connector that is off — so nothing loads, reasons or writes;
  * decisions already in flight can still be recorded; nothing is lost.
Capability owners switch their capability, group owners their group; the
platform support role (HELIX_ADMIN_ROLE) any of them, and connectors.

Spend limits — manifest `limits` (per case, per day): model cost recorded on
findings and chat answers is added up; over a limit, groups that would go to
the model are escalated to a person with the reason, and chat answers from
the case's record only.
"""

import time
from datetime import datetime, timezone

from sqlalchemy import Float, cast, func, select

from helix.config import settings
from helix.db import get_session
from helix.entitlement import Caller
from helix.models import Case, CaseMessage, ProposalGroup, Switch

KINDS = ("capability", "group", "connector")
_cache: dict[tuple[str, str], tuple[float, Switch | None]] = {}
TTL = 5.0


class SwitchedOff(RuntimeError):
    pass


async def state(kind: str, target: str) -> Switch | None:
    hit = _cache.get((kind, target))
    if hit and time.monotonic() - hit[0] < TTL:
        return hit[1]
    async with get_session() as s:
        row = await s.get(Switch, (kind, target))
    _cache[(kind, target)] = (time.monotonic(), row)
    return row


async def off_reason(kind: str, target: str) -> str | None:
    row = await state(kind, target)
    return f"{kind} {target} is switched off: {row.reason}" if row and row.off else None


async def check_open(capability_id: str, team_group: str | None) -> None:
    for kind, target in (("capability", capability_id),
                         *((("group", f"{capability_id}/{team_group}"),) if team_group else ())):
        if why := await off_reason(kind, target):
            raise SwitchedOff(why)


async def can_switch(caller: Caller, kind: str, target: str) -> bool:
    if settings().admin_role in caller.roles:
        return True
    if kind == "connector":
        return False
    from helix import capabilities
    from helix import groups as team_groups

    capability_id = target.split("/", 1)[0]
    try:
        _, m = await capabilities.active(capability_id)
    except Exception:
        return False
    if kind == "capability":
        return capabilities.is_owner(caller, m)
    try:
        _, cfg, _ = await team_groups.active_group(capability_id, target.split("/", 1)[1])
    except Exception:
        return False
    return capabilities.is_owner(caller, m) or team_groups.is_group_owner(caller, cfg)


async def set_switch(caller: Caller, kind: str, target: str, off: bool, reason: str) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind is one of {', '.join(KINDS)}")
    reason = (reason or "").strip()
    if off and not reason:
        raise ValueError("say why it is switched off")
    if not await can_switch(caller, kind, target):
        raise PermissionError(f"{caller.user_id} may not switch {kind} {target}")
    now = datetime.now(timezone.utc).isoformat()
    async with get_session() as s:
        row = await s.get(Switch, (kind, target))
        entry = {"off": off, "reason": reason, "by": caller.user_id, "at": now}
        if row is None:
            row = Switch(kind=kind, target=target, off=off, reason=reason, set_by=caller.user_id, history=[entry])
            s.add(row)
        else:
            row.off, row.reason, row.set_by = off, reason, caller.user_id
            row.history = [*(row.history or []), entry]
        await s.commit()
    _cache.pop((kind, target), None)
    return {"kind": kind, "target": target, "off": off, "reason": reason, "set_by": caller.user_id}


async def all_switches() -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(Switch).order_by(Switch.kind, Switch.target))).scalars().all()
    return [{"kind": r.kind, "target": r.target, "off": r.off, "reason": r.reason, "set_by": r.set_by,
             "set_at": r.set_at, "history": r.history} for r in rows]


# ---------- spend ----------

def _cost(col):
    return func.coalesce(func.sum(cast(col["usage"]["cost_usd"].astext, Float)), 0.0)


async def spent(capability_id: str, *, case_id: str | None = None, since: datetime | None = None) -> float:
    """Model cost recorded for a capability (or one case), from findings and chat answers."""
    async with get_session() as s:
        q1 = select(_cost(ProposalGroup.finding)).join(Case, Case.case_id == ProposalGroup.case_id).where(
            Case.capability_id == capability_id)
        q2 = select(_cost(CaseMessage.meta)).join(Case, Case.case_id == CaseMessage.case_id).where(
            Case.capability_id == capability_id)
        if case_id:
            q1, q2 = q1.where(Case.case_id == case_id), q2.where(Case.case_id == case_id)
        if since:
            q1, q2 = q1.where(Case.opened_at >= since), q2.where(CaseMessage.created_at >= since)
        return float((await s.execute(q1)).scalar_one()) + float((await s.execute(q2)).scalar_one())


async def over_budget(m, case_id: str) -> str | None:
    """Why the model may not be called now, or None."""
    lim = m.limits
    if lim.max_cost_usd_per_case is not None:
        used = await spent(m.id, case_id=case_id)
        if used >= lim.max_cost_usd_per_case:
            return f"BUDGET_EXCEEDED: this case has used ${used:.2f} of its ${lim.max_cost_usd_per_case:.2f}"
    if lim.max_cost_usd_per_day is not None:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        used = await spent(m.id, since=start)
        if used >= lim.max_cost_usd_per_day:
            return f"BUDGET_EXCEEDED: {m.id} has used ${used:.2f} of its ${lim.max_cost_usd_per_day:.2f} today"
    return None
