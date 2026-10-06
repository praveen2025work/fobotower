"""Escalation tickets: after review, a ticket for the team that owns a problem.

Configured per capability (or group) by `escalation` in the manifest:

    escalation:
      tool: ticketing.create_ticket          # a write tool on a ticketing connector
      when: "verdict == 'DO_NOT_POST' or status == 'escalated'"
      args:
        team: "{escalate_to}"
        title: "{subject}: {label}"
        description: "{comment}"
        priority: P3

`when` is evaluated over each decided group: its key fields, total, count,
label, verdict, status (proposed|escalated), action (approve|reject),
category, category_name, side, escalate_to, policy. Argument strings are
templates over the same fields plus case_id, subject, comment, decided_by and
the case key; "$case.<field>" works as in `publish`.

The call goes through the gateway as the record step ("escalate"), allowed
only for this one write tool and only after people decided; it is idempotent
per case and group, and recorded (aof_ticket) whether it worked or not —
a failed ticket never fails the case.
"""

import logging

from sqlalchemy import select

from agent_one_finance import gateway, rules
from agent_one_finance.db import get_session
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Ticket

log = logging.getLogger("agent_one_finance.escalation")


def _env(m: Manifest, state: dict, group: dict, finding: dict, decision: dict) -> dict:
    case_key = state["case_key"]
    try:
        subject = m.case.subject.format(**case_key) if m.case.subject else ""
    except (KeyError, IndexError):
        subject = ""
    return {**case_key, **group.get("group_key", {}),
            "case_id": state["case_id"], "subject": subject, "label": group.get("label", ""),
            "total": group.get("total"), "count": group.get("count", len(group.get("item_ids", []))),
            "verdict": finding.get("verdict"), "status": finding.get("status"),
            "category": finding.get("category"), "category_name": finding.get("category_name"),
            "side": finding.get("side"), "escalate_to": finding.get("escalate_to") or "",
            "action": decision.get("action"), "decided_by": decision.get("decided_by", ""),
            "comment": decision.get("comment") or finding.get("comment") or finding.get("reason") or "",
            "policy": m.policy_values()}


def _args(spec_args: dict, env: dict, case_key: dict) -> dict:
    out = {}
    for k, v in spec_args.items():
        if isinstance(v, str) and v.startswith("$case."):
            v = case_key[v[6:]]
        elif isinstance(v, str) and v.startswith("$") and v[1:] in env:
            v = env[v[1:]]
        elif isinstance(v, str):
            v = rules.render(v, env)
        out[k] = v
    return out


async def raise_tickets(m: Manifest, state: dict, ctx: gateway.CallContext) -> list[dict]:
    """One ticket per decided group that matches `escalation.when` (once)."""
    if not m.escalation:
        return []
    findings = state.get("findings", {})
    groups = {g["group_id"]: g for g in state.get("groups", [])}
    async with get_session() as s:
        done = {t.group_id for t in (await s.execute(select(Ticket).where(
            Ticket.case_id == state["case_id"], Ticket.status == "raised"))).scalars()}
    out = []
    for d in state.get("decisions", []):
        g = groups.get(d["group_id"])
        if g is None or d["group_id"] in done:
            continue
        env = _env(m, state, g, findings.get(d["group_id"], {}), d)
        try:
            if not rules.evaluate(m.escalation.when, env):
                continue
        except Exception:
            log.exception("escalation.when failed for %s/%s", state["case_id"], d["group_id"])
            continue
        args = _args(m.escalation.args, env, state["case_key"])
        ctx.write_approved_by = d.get("decided_by") or None
        row = Ticket(case_id=state["case_id"], group_id=d["group_id"], tool=m.escalation.tool,
                     status="raised")
        try:
            receipt = await gateway.call(ctx, m.escalation.tool, args,
                                         idempotency_key=f"ticket:{state['case_id']}:{d['group_id']}")
            row.reference = str(receipt.get("reference") or receipt.get("id") or "")[:128] or None
            row.url = receipt.get("url")
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            row.status, row.error = "failed", str(e)
        async with get_session() as s:
            await s.merge(row)
            await s.commit()
        out.append({"group_id": row.group_id, "status": row.status, "reference": row.reference})
    return out


async def for_case(case_id: str) -> dict[str, dict]:
    async with get_session() as s:
        rows = (await s.execute(select(Ticket).where(Ticket.case_id == case_id))).scalars().all()
    return {t.group_id: {"reference": t.reference, "url": t.url, "status": t.status,
                         "error": t.error, "tool": t.tool, "raised_at": t.raised_at} for t in rows}
