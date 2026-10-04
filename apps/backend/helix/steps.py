"""The core step library. Every capability's workflow is a list of these.

Each step reads the pinned manifest from the run's state and is driven only
by it — no capability-specific code. Steps that touch data do so through the
MCP gateway; steps that persist write helix_* rows so the console and the
audit read real records, not the checkpoint.
"""

import hashlib
import re
from typing import Any, TypedDict

from sqlalchemy import select

from helix import gateway, knowledge, rules
from helix.db import get_session
from helix.entitlement import Caller
from helix.governance import Protector, fields_for
from helix.llm import ReasonRequest, llm
from helix.manifest import Manifest, ToolCallSpec
from helix.models import Case, CaseItem, ProposalGroup, ToolCall
from helix.observability import span

ESCALATED = "escalated"


class CaseState(TypedDict, total=False):
    # identity — supplied when the case opens
    case_id: str
    capability_id: str
    manifest_version: int
    manifest: dict
    case_key: dict
    caller: dict
    # produced by steps
    items: list[dict]
    groups: list[dict]
    findings: dict[str, dict]
    draft: dict
    validation_errors: list[str]
    review_cycles: int
    decisions: list[dict]          # written on resume, from helix_decision
    publish_approval: dict         # written on resume, from helix_publish_approval
    published: list[dict]
    outcome: str | None
    escalation_reason: str | None


# ---------- helpers ----------

def _manifest(state: CaseState) -> Manifest:
    return Manifest.model_validate(state["manifest"])


def _caller(state: CaseState) -> Caller:
    c = state["caller"]
    return Caller(c["user_id"], frozenset(c["roles"]),
                  {k: frozenset(v) for k, v in c["data_scopes"].items()})


def _ctx(state: CaseState, step: str, tools: set[str] | None = None) -> gateway.CallContext:
    m = _manifest(state)
    return gateway.CallContext(
        capability_id=state["capability_id"], caller=_caller(state),
        allowed_tools=frozenset(tools if tools is not None else m.read_tools()),
        case_id=state["case_id"], requested_by=step,
    )


def _args(spec: ToolCallSpec, case_key: dict) -> dict:
    return {k: case_key[v[6:]] if isinstance(v, str) and v.startswith("$case.") else v
            for k, v in spec.args.items()}


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _escalate(reason: str, detail: str = "") -> dict:
    return {"outcome": ESCALATED, "escalation_reason": f"{reason}: {detail}" if detail else reason}


async def _save_items(case_id: str, items: list[dict]) -> None:
    async with get_session() as s:
        for it in items:
            await s.merge(CaseItem(case_id=case_id, item_id=it["item_id"], payload=it))
        await s.commit()


async def _save_group_finding(case_id: str, group_id: str, finding: dict) -> None:
    async with get_session() as s:
        row = await s.get(ProposalGroup, (case_id, group_id))
        row.finding = finding
        await s.commit()


# ---------- steps ----------

async def load(state: CaseState) -> dict:
    m = _manifest(state)
    try:
        result = await gateway.call(_ctx(state, "load"), m.items.load.tool,
                                    _args(m.items.load, state["case_key"]))
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return _escalate("LOAD_FAILED", str(e))
    items = [{**row, "item_id": str(row[m.items.id_field])} for row in result.get("rows", [])]
    await _save_items(state["case_id"], items)
    return {"items": items}


async def match(state: CaseState) -> dict:
    m = _manifest(state)
    spec = m.match
    ctx = _ctx(state, "match")
    try:
        left = (await gateway.call(ctx, spec.left.tool, _args(spec.left, state["case_key"]))).get("rows", [])
        right = (await gateway.call(ctx, spec.right.tool, _args(spec.right, state["case_key"]))).get("rows", [])
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return _escalate("LOAD_FAILED", str(e))
    key = lambda r: tuple(str(r.get(k)) for k in spec.keys)  # noqa: E731
    lidx, ridx = {key(r): r for r in left}, {key(r): r for r in right}
    items = []
    for k in sorted(set(lidx) | set(ridx)):
        lrow, rrow = lidx.get(k), ridx.get(k)
        la = _num(lrow[spec.amount_field]) if lrow else None
        ra = _num(rrow[spec.amount_field]) if rrow else None
        if lrow and rrow and abs(la - ra) <= spec.tolerance:
            continue
        status = ("missing_" + spec.right_label if rrow is None
                  else "missing_" + spec.left_label if lrow is None else "amount_break")
        base = lrow or rrow
        items.append({
            "item_id": "|".join(k), **{f: base.get(f) for f in spec.keys},
            f"{spec.left_label}_amount": la, f"{spec.right_label}_amount": ra,
            "difference": round((la or 0.0) - (ra or 0.0), 2), "break_type": status,
            **{f: v for f, v in base.items() if f not in spec.keys and f != spec.amount_field},
        })
    await _save_items(state["case_id"], items)
    return {"items": items}


async def compare(state: CaseState) -> dict:
    spec = _manifest(state).compare
    items = [{**it, spec.as_: round(_num(it.get(spec.measure)) - _num(it.get(spec.baseline)), 2)}
             for it in state["items"]]
    await _save_items(state["case_id"], items)
    return {"items": items}


def _group_id(values: tuple, fields: list[str], protected: set[str]) -> str:
    """Readable ("6100") unless a grouping field is protected data — then an
    opaque hash, so names never travel in ids, URLs or span attributes."""
    if any(f.lower() in protected for f in fields):
        return "g-" + hashlib.sha1("|".join(values).encode()).hexdigest()[:10]
    return "-".join(values) or "all"


async def group(state: CaseState) -> dict:
    m = _manifest(state)
    policy = m.policy_values()
    in_scope = [it for it in state["items"]
                if not m.items.in_scope or rules.evaluate(m.items.in_scope, {**it, "policy": policy})]
    mask_f, pseudo_f = fields_for(m.tools_used())
    protected = mask_f | pseudo_f
    buckets: dict[tuple, list[dict]] = {}
    for it in in_scope:
        buckets.setdefault(tuple(str(it.get(f)) for f in m.group_by), []).append(it)
    groups = []
    async with get_session() as s:
        for values, members in sorted(buckets.items()):
            group_key = dict(zip(m.group_by, values))
            group_id = _group_id(values, m.group_by, protected)
            label = ", ".join(f"{k} {v}" for k, v in group_key.items()) or "All items"
            total = round(sum(_num(it.get(m.items.amount_field)) for it in members), 2) \
                if m.items.amount_field else None
            priors = await knowledge.similar_decisions(
                state["capability_id"], group_key, exclude_case=state["case_id"])
            g = {"group_id": group_id, "label": label, "group_key": group_key,
                 "item_ids": [it["item_id"] for it in members], "count": len(members),
                 "total": total, "priors": priors}
            groups.append(g)
            await s.merge(ProposalGroup(case_id=state["case_id"], group_id=group_id, label=label,
                                        group_key=group_key, item_ids=g["item_ids"],
                                        priors=priors, finding=None))
        await s.commit()
    return {"groups": groups}


async def reason(state: CaseState) -> dict:
    m = _manifest(state)
    policy = m.policy_values()
    items = {it["item_id"]: it for it in state["items"]}
    findings: dict[str, dict] = {}
    for g in state["groups"]:
        env = {**g["group_key"], "total": g["total"], "count": g["count"],
               "label": g["label"], "policy": policy}
        with span("reason.group", case_id=state["case_id"], group_id=g["group_id"]) as sp:
            finding = None
            for rule in m.rules:
                if rules.evaluate(rule.when, env):
                    finding = {"status": rule.then.status, "decided_by": "rule", "rule": rule.id,
                               "comment": rules.render(rule.then.comment, env),
                               "reason": rule.then.reason}
                    break
            if finding is None and m.reasoning.reasoner == "none":
                finding = {"status": ESCALATED, "decided_by": "none", "comment": "",
                           "reason": "NO_REASONER"}
            if finding is None:
                # The model sees protected data only (governance.yaml): masked fields
                # never, pseudonymized ones as per-case tokens it can still pass to
                # tools. Its answer is re-identified before validation and review.
                guard = Protector.for_tools(m.tools_used(), state["case_id"])
                ctx = _ctx(state, "reason", set(m.reasoning.tools))
                ctx.protector = guard
                group_view = {**g, "items": [
                    {**items[i], "amount": items[i].get(m.items.amount_field)}
                    for i in g["item_ids"]]}
                request = ReasonRequest(
                    capability_id=state["capability_id"], case_id=state["case_id"],
                    case_key=guard.protect(state["case_key"]), skill=m.reasoning.skill,
                    group={**guard.protect(group_view),
                           "label": guard.protect_text(g["label"], g["group_key"]),
                           "priors": [{**p, "comment": guard.protect_text(
                               p.get("comment", ""), g["group_key"])} for p in g["priors"]]},
                    allowed_tools=list(m.reasoning.tools), output=m.reasoning.output)
                adapter = llm()
                try:
                    res = await adapter.reason(request, gateway.invoker(ctx))
                    finding = {"status": res.status, "decided_by": f"llm:{adapter.name}",
                               "comment": guard.reveal(res.comment),
                               "reason": guard.reveal(res.reason) if res.reason else None,
                               "model": res.model, "usage": res.usage}
                except (gateway.ToolDenied, gateway.ToolFailed) as e:
                    finding = {"status": ESCALATED, "decided_by": f"llm:{adapter.name}",
                               "comment": "", "reason": f"TOOL_ERROR: {e}"}
                except Exception as e:  # the model must never fail the run silently
                    finding = {"status": ESCALATED, "decided_by": f"llm:{adapter.name}",
                               "comment": "", "reason": f"REASONER_ERROR: {type(e).__name__}: {e}"}
            sp.set_attribute("helix.decided_by", finding["decided_by"])
            sp.set_attribute("helix.status", finding["status"])
        findings[g["group_id"]] = finding
        await _save_group_finding(state["case_id"], g["group_id"], finding)
    return {"findings": findings}


async def draft(state: CaseState) -> dict:
    m = _manifest(state)
    findings = state.get("findings", {})
    proposed = sum(1 for f in findings.values() if f["status"] == "proposed")
    escalated = sum(1 for f in findings.values() if f["status"] == ESCALATED)
    in_scope = sum(g["count"] for g in state["groups"])
    d = {
        "headline": f"{in_scope} of {len(state['items'])} {m.case.item_label.lower()}(s) in scope, "
                    f"in {len(state['groups'])} group(s): {proposed} proposed, {escalated} escalated.",
        "groups": [{"group_id": g["group_id"], "label": g["label"],
                    "comment": findings.get(g["group_id"], {}).get("comment", "")}
                   for g in state["groups"]],
    }
    async with get_session() as s:
        (await s.get(Case, state["case_id"])).draft = d
        await s.commit()
    return {"draft": d}


_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _numbers_in(value: Any, out: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        out.update({round(float(value), 2), round(abs(float(value)), 2)})
    elif isinstance(value, str):
        for n in _NUMBER.findall(value):
            _numbers_in(float(n.replace(",", "")), out)
    elif isinstance(value, dict):
        for v in value.values():
            _numbers_in(v, out)
    elif isinstance(value, (list, tuple)):
        _numbers_in(len(value), out)
        for v in value:
            _numbers_in(v, out)


async def validate(state: CaseState) -> dict:
    """Gate: every figure in a proposed finding must trace to data the run read."""
    grounded: set[float] = set()
    _numbers_in([state["case_key"], state["items"], state["groups"]], grounded)
    async with get_session() as s:
        results = (await s.execute(select(ToolCall.result).where(
            ToolCall.case_id == state["case_id"], ToolCall.allowed.is_(True),
            ToolCall.result.is_not(None)))).scalars().all()
    _numbers_in(list(results), grounded)

    findings = dict(state.get("findings", {}))
    errors = []
    for group_id, f in findings.items():
        if f["status"] != "proposed":
            continue
        cited: set[float] = set()
        for n in _NUMBER.findall(f["comment"]):
            cited.add(round(float(n.replace(",", "")), 2))
        missing = sorted(n for n in cited if n not in grounded)
        if missing:
            f = {**f, "status": ESCALATED,
                 "reason": f"UNGROUNDED_FIGURE: {', '.join(f'{n:,.2f}' for n in missing)}"}
            findings[group_id] = f
            errors.append(f"{group_id}: {f['reason']}")
            await _save_group_finding(state["case_id"], group_id, f)
    return {"findings": findings, "validation_errors": errors}


async def review(state: CaseState) -> dict:
    """Gate: the run pauses before this step until people decide."""
    return {"review_cycles": state.get("review_cycles", 0) + 1}


async def record(state: CaseState) -> dict:
    """Gate: approved decisions become priors the next run reads."""
    findings = state.get("findings", {})
    groups = {g["group_id"]: g for g in state["groups"]}
    for d in state.get("decisions", []):
        g = groups.get(d["group_id"])
        if g is None:
            continue
        await knowledge.record_decision(
            state["capability_id"], g["group_key"], case_id=state["case_id"],
            group_id=d["group_id"], action=d["action"],
            comment=d.get("comment") or findings.get(d["group_id"], {}).get("comment", ""),
            decided_by=d["decided_by"])
    if "publish" in _manifest(state).steps:
        return {"outcome": "recorded"}       # the run pauses before publish
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        case.status, case.outcome = "completed", "completed"
        await s.commit()
    return {"outcome": "completed"}


def _publish_args(spec_args: dict, state: CaseState, tokens: dict[str, Any]) -> dict:
    """Resolve a publish spec's arguments: literals, "$case.<field>",
    "$group.<field>" and the named tokens (see PublishSpec)."""
    case_key = state["case_key"]
    out = {}
    for k, v in spec_args.items():
        if isinstance(v, str) and v.startswith("$case."):
            v = case_key[v[6:]]
        elif isinstance(v, str) and v.startswith("$group."):
            v = tokens["$group"][v[7:]]
        elif isinstance(v, str) and v in tokens:
            v = tokens[v]
        out[k] = v
    return out


def _subject(m: Manifest, case_key: dict) -> str:
    try:
        return m.case.subject.format(**case_key)
    except (KeyError, IndexError, ValueError):
        return ", ".join(f"{k} {v}" for k, v in case_key.items())


def _approved(state: CaseState, m: Manifest) -> list[tuple[dict, dict, str]]:
    """(group, decision, approved explanation) for every approved group."""
    findings = state.get("findings", {})
    groups = {g["group_id"]: g for g in state["groups"]}
    return [(groups[d["group_id"]], d,
             d.get("comment") or findings.get(d["group_id"], {}).get("comment", ""))
            for d in state.get("decisions", [])
            if d["action"] == "approve" and d["group_id"] in groups]


async def publish(state: CaseState) -> dict:
    """Write the approved results back through the capability's write tool —
    one call per approved group, or one for the whole case (a report).
    Runs only after a second person released it (publish_approval)."""
    m = _manifest(state)
    approval = state.get("publish_approval") or {}
    ctx = _ctx(state, "publish", {m.publish.tool})
    ctx.requested_by, ctx.write_approved_by = "publish", approval.get("approved_by")
    approved = _approved(state, m)
    common = {"$case_id": state["case_id"], "$subject": _subject(m, state["case_key"])}
    calls: list[tuple[str | None, dict]] = []
    if m.publish.per == "case":
        items = {it["item_id"]: it for it in state.get("items", [])}
        columns = m.items.display or []
        sections = [{"heading": g["label"], "body": comment, "decided_by": d["decided_by"],
                     "columns": columns,
                     "rows": [{c: items[i].get(c) for c in columns} for i in g["item_ids"] if i in items]}
                    for g, d, comment in approved]
        sign_off = [{"step": f"review: {g['label']}", "by": d["decided_by"], "at": d.get("decided_at", "")}
                    for g, d, _ in approved]
        sign_off.append({"step": "release", "by": approval.get("approved_by"),
                         "at": approval.get("approved_at", "")})
        if approved:
            calls.append((None, _publish_args(m.publish.args, state, {
                **common, "$approved": sections, "$sign_off": sign_off})))
    else:
        for g, _, comment in approved:
            calls.append((g["group_id"], _publish_args(m.publish.args, state, {
                **common, "$group": g["group_key"], "$comment": comment})))
    published, failed = [], []
    for group_id, args in calls:
        try:
            receipt = await gateway.call(ctx, m.publish.tool, args)
            published.append({"group_id": group_id, "receipt": receipt})
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            failed.append(f"{group_id or 'case'}: {e}")
    outcome = "published" if not failed else "publish_failed"
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        case.status, case.outcome = ("completed", outcome) if not failed else ("failed", outcome)
        case.error = "; ".join(failed) or None
        await s.commit()
    return {"outcome": outcome, "published": published}


async def escalate(state: CaseState) -> dict:
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        case.status, case.outcome, case.error = ESCALATED, ESCALATED, state.get("escalation_reason")
        await s.commit()
    return {}
