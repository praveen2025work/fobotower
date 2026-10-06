"""Review policy shared by every capability: what a group needs from its
reviewer, and who may decide (including a colleague covering for someone away).

Flags on a group's finding (`flags`):
  confirmation  a verdict flagged "requires controller confirmation" (unset policy)
  judgement     a judgement call: the model investigated, an SME decides
  escalated     escalated by a rule, the playbook or the model
  model         proposed by the model

The manifest decides what each flag means for the reviewer:
  review.bulk_exclude      flags "Approve all" leaves for one-by-one review
  review.confirm           what approving a "confirmation" group needs
  review.allow_delegation  whether a reviewer may hand reviews to a colleague
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller, _caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Delegation

FLAGS = ("confirmation", "judgement", "escalated", "model")


class ReviewError(ValueError):
    pass


def flags(finding: dict | None) -> list[str]:
    f = finding or {}
    out = []
    if f.get("requires_confirmation"):
        out.append("confirmation")
    if f.get("sme_review"):
        out.append("judgement")
    if f.get("status") == "escalated":
        out.append("escalated")
    if str(f.get("decided_by", "")).startswith("llm:"):
        out.append("model")
    return out


def bulk_blockers(m: Manifest, finding: dict | None) -> list[str]:
    """Why "Approve all" must leave this group for one-by-one review (empty: it may not)."""
    f = finding or {}
    out = [x for x in flags(finding) if x in m.review.bulk_exclude]
    if f.get("reserved"):
        out.append("reserved")
    if (f.get("authority") or {}).get("bulk") is False:
        out.append("authority")
    return out


def confirmation_problem(m: Manifest, finding: dict | None, action: str, confirmed: bool,
                         comment: str | None) -> str | None:
    if action != "approve" or "confirmation" not in flags(finding) or m.review.confirm == "none":
        return None
    why = (finding or {}).get("requires_confirmation", "")
    if not confirmed:
        return f"this verdict needs your explicit confirmation ({why})"
    if m.review.confirm == "tick_and_comment" and not comment:
        return "confirming this verdict needs your explanation"
    return None


# ---------- delegation ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def active_from(user_ids: list[str] | None = None, *, to_user: str | None = None) -> list[Delegation]:
    async with get_session() as s:
        q = select(Delegation).where(Delegation.revoked_at.is_(None), Delegation.starts_at <= _now(),
                                     Delegation.until > _now())
        if to_user:
            q = q.where(Delegation.to_user == to_user)
        if user_ids is not None:
            q = q.where(Delegation.from_user.in_(user_ids))
        return list((await s.execute(q.order_by(Delegation.created_at))).scalars())


async def covering_for(caller: Caller) -> list[Caller]:
    """The absent reviewers this caller is covering for now, as they were entitled."""
    return [_caller(d.from_user, d.from_entitlement) for d in await active_from(to_user=caller.user_id)]


async def acting_as(caller: Caller, m: Manifest, case_key: dict, may_see_case) -> tuple[bool, str | None]:
    """(may decide, on behalf of whom). A reviewer decides as themselves; with
    review.allow_delegation, a colleague may decide for an absent reviewer
    whose roles and data scope cover the case."""
    if may_see_case(caller, m, case_key) and caller.has_any_role(m.review.roles):
        return True, None
    if not m.review.allow_delegation:
        return False, None
    for absent in await covering_for(caller):
        if may_see_case(absent, m, case_key) and absent.has_any_role(m.review.roles):
            return True, absent.user_id
    return False, None


async def delegate(caller: Caller, to_user: str, until: datetime, reason: str | None,
                   starts_at: datetime | None = None) -> dict:
    to_user = (to_user or "").strip()
    if not to_user or to_user == caller.user_id:
        raise ReviewError("choose a colleague to cover for you")
    starts_at = starts_at or _now()
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if until <= starts_at:
        raise ReviewError("the cover must end after it starts")
    if (until - starts_at).days > 60:
        raise ReviewError("cover can last at most 60 days")
    row = Delegation(delegation_id=uuid.uuid4().hex, from_user=caller.user_id, to_user=to_user,
                     starts_at=starts_at, until=until, reason=(reason or "").strip() or None,
                     from_entitlement={k: v for k, v in caller.as_dict().items() if k != "user_id"})
    async with get_session() as s:
        s.add(row)
        await s.commit()
    return _row(row)


async def revoke(caller: Caller, delegation_id: str) -> None:
    async with get_session() as s:
        row = await s.get(Delegation, delegation_id)
        if row is None or caller.user_id not in (row.from_user, row.to_user):
            raise LookupError(delegation_id)
        row.revoked_at = _now()
        await s.commit()


async def mine(caller: Caller) -> dict:
    """Cover I gave (away) and cover I am giving (covering), current and upcoming."""
    async with get_session() as s:
        rows = (await s.execute(select(Delegation).where(
            Delegation.revoked_at.is_(None), Delegation.until > _now(),
            (Delegation.from_user == caller.user_id) | (Delegation.to_user == caller.user_id))
            .order_by(Delegation.starts_at))).scalars().all()
    return {"away": [_row(r) for r in rows if r.from_user == caller.user_id],
            "covering": [_row(r) for r in rows if r.to_user == caller.user_id]}


def _row(r: Delegation) -> dict:
    return {"delegation_id": r.delegation_id, "from_user": r.from_user, "to_user": r.to_user,
            "starts_at": r.starts_at, "until": r.until, "reason": r.reason,
            "active": r.starts_at <= _now() < r.until and r.revoked_at is None}
