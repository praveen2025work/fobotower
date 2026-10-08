"""The core step library. Every capability's workflow is a list of these.

Each step reads the pinned manifest from the run's state and is driven only
by it — no capability-specific code. Steps that touch data do so through the
MCP gateway; steps that persist write aof_* rows so the console and the
audit read real records, not the checkpoint.
"""

import asyncio
import hashlib
import os
from collections import Counter
import re
from typing import Any, TypedDict

from sqlalchemy import select

from agent_one_finance import asks, controls, follow_through, gateway, knowledge, rules
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.governance import Protector, fields_for
from agent_one_finance.llm import ReasonRequest, SessionRequest, llm, run_session
from agent_one_finance.manifest import Manifest, ToolCallSpec
from agent_one_finance.models import Case, CaseItem, ProposalGroup, ToolCall
from agent_one_finance.observability import span

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
    decisions: list[dict]          # written on resume, from aof_decision
    publish_approval: dict         # written on resume, from aof_publish_approval
    follow_up_of: str | None       # a follow-up case: the case of the same key it follows
    gates_passed: list[str]        # tollgates a person passed, in order (aof_gate_decision)
    gate_notes: list[dict]         # what they wrote there: [{step, by, comment}] — context for the model
    published: list[dict]
    datasets: dict[str, list[dict]]   # named data sets beside the items (dataset, aggregate steps)
    skipped: list[str]                # steps whose `when` did not hold this run
    events: dict[str, dict]           # what each `await` step received (an event, child outcomes, a timeout)
    spawned: bool                     # a `spawn` step opened child cases
    model_context: list[dict]         # data sets the model sees when it investigates (e.g. a timeline)
    session_summary: str              # what the `agent` step's session said about the whole case
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
    if state.get("follow_up_of"):
        # Late items only: what no case for this key (the first, or an earlier
        # follow-up) has taken already.
        seen = await _items_already_taken(state["follow_up_of"], state["case_id"])
        items = [it for it in items if it["item_id"] not in seen]
    items = await follow_through.carry(state, m, items)
    await _save_items(state["case_id"], items)
    return {"items": items}


async def _items_already_taken(root: str, case_id: str) -> set[str]:
    from agent_one_finance.models import Case, CaseItem
    async with get_session() as s:
        cases = select(Case.case_id).where(
            ((Case.case_id == root) | (Case.root_case_id == root) | (Case.follow_up_of == root))
            & (Case.case_id != case_id))
        return set((await s.execute(select(CaseItem.item_id).where(CaseItem.case_id.in_(cases)))).scalars())


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
    items = await follow_through.carry(state, m, items)
    await _save_items(state["case_id"], items)
    return {"items": items}


async def enrich(state: CaseState) -> dict:
    """Join more facts onto the items, one read per case per source (e.g. the
    break snapshots cause checks need). An item with no row is marked."""
    m = _manifest(state)
    if not m.enrich:
        return {}                     # not configured: nothing to do
    items = [dict(it) for it in state["items"]]
    ctx = _ctx(state, "enrich")
    for spec in m.enrich:
        try:
            rows = (await gateway.call(ctx, spec.tool, _args(spec, state["case_key"]))).get("rows", [])
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            return _escalate("ENRICH_FAILED", str(e))
        index = {tuple(str(r.get(k)) for k in spec.keys): r for r in rows}
        for it in items:
            row = index.get(tuple(str(it.get(k)) for k in spec.keys))
            if row is None:
                it["enrich_missing"] = [*it.get("enrich_missing", []), spec.tool]
                continue
            for k, v in row.items():
                if k not in spec.keys:
                    it[f"{spec.prefix}{k}"] = v
    await _save_items(state["case_id"], items)
    return {"items": items}


async def classify(state: CaseState) -> dict:
    """Run the playbook's cause checks on every item. All checks run and all
    results are kept; the first positive (in playbook order) is the cause, and
    sets the item's category, side and escalation team."""
    m = _manifest(state)
    if m.playbook is None:
        return {}                     # not configured: nothing to do
    pb = m.playbook
    policy = m.policy_values()
    items = []
    for it in state["items"]:
        env = {**it, "policy": policy}
        results = []
        for c in pb.checks:
            try:
                positive = bool(rules.evaluate(c.when, env))
            except Exception:   # a missing field is "not shown", never a crash
                positive = False
            results.append({"id": c.id, "positive": positive,
                            "reason": rules.render(c.reason, env) if positive else ""})
        cause = next((pb.checks[i] for i, r in enumerate(results) if r["positive"]), None)
        category = cause.category if cause else pb.default_category
        side = cause.side if cause else "UNKNOWN"
        reason = next((r["reason"] for r in results if r["positive"]), "No cause check explains it")
        tests = _run_tests(pb, env, policy)
        finding = _test_finding(pb, env, tests)
        if cause is None and finding and finding.indicates:
            # a test's evidence explains what no cause check did (e.g. FO-6 finding A)
            category, side = finding.indicates, finding.side
            reason = f"{finding.test} finding {finding.id}: {finding.description}"
        cat = pb.categories[category]
        items.append({**it, "checks": results, "cause": cause.id if cause else None,
                      "category": category, "category_name": cat.name, "side": side,
                      "determinism": cat.determinism, "escalate_to": cat.escalate_to,
                      "cause_reason": reason, "tests": tests,
                      "test_finding": ({"id": finding.id, "test": finding.test,
                                        "description": finding.description} if finding else None),
                      "blocked_by": _blocks(pb, tests)})
    await _save_items(state["case_id"], items)
    return {"items": items}


def _run_tests(pb, env: dict, policy: dict) -> list[dict]:
    """Every validation test on one item: fail, pass, or not run (and why).
    A test whose evidence is missing, or whose threshold is unset (P1), is not
    run — it never passes by default."""
    out = []
    for t in pb.tests:
        row = {"id": t.id, "side": t.side, "validates": t.validates, "check": t.check,
               "on_fail": t.on_fail, "evidence": t.evidence}
        missing = [f for f in t.needs if env.get(f) is None]
        unset = [p for p in t.policy if policy.get(p) is None]
        if missing:
            row.update(status="not_run", why=f"evidence missing: {', '.join(t.evidence) or ', '.join(missing)}")
        elif unset:
            row.update(status="not_run", why=f"policy unset: {', '.join(unset)}")
        else:
            try:
                failed = bool(rules.evaluate(t.fails_when, env))
            except Exception as e:
                row.update(status="not_run", why=f"cannot evaluate: {e}")
            else:
                row["status"] = "fail" if failed else "pass"
        out.append(row)
    return out


def _test_finding(pb, env: dict, tests: list[dict]):
    ran = {t["id"] for t in tests if t["status"] != "not_run"}
    for f in pb.findings:
        if f.test in ran:
            try:
                if rules.evaluate(f.when, env):
                    return f
            except Exception:
                continue
    return None


def _blocks(pb, tests: list[dict]) -> list[str]:
    """Why an adjustment must be held: a blocking test failed, or a failed test
    needs another test that could not run."""
    by_id = {t["id"]: t for t in tests}
    out = []
    for spec in pb.tests:
        t = by_id[spec.id]
        if t["status"] != "fail":
            continue
        if spec.blocks_post:
            out.append(f"{spec.id} failed: {spec.on_fail or spec.check}")
        for req in spec.requires_on_fail:
            if by_id.get(req, {}).get("status") == "not_run":
                out.append(f"{spec.id} failed and needs {req}, which could not run ({by_id[req].get('why')})")
    return out


async def resolve(state: CaseState) -> dict:
    """Reference lookups per item from the knowledge graph, as of the case's
    business date: e.g. a book's desk, or the team a desk escalates to."""
    m = _manifest(state)
    if not m.resolve:
        return {}                     # not configured: nothing to do
    as_of = state["case_key"].get(m.knowledge.as_of) if m.knowledge.as_of else None
    items = [dict(it) for it in state["items"]]
    for spec in m.resolve:
        starts = {i: rules.render(spec.node, it) for i, it in enumerate(items)}
        found = await knowledge.walk(m.knowledge.reference, set(starts.values()), spec.path, as_of=as_of)
        for i, sid in starts.items():
            node = found.get(sid)
            items[i][spec.as_] = (None if node is None
                                  else node.node_id.split(":", 1)[-1] if spec.take == "id"
                                  else node.attrs.get(spec.take))
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


def group_label(m: Manifest, group_key: dict) -> str:
    """A group's name: the manifest's `group_label` template over its key and,
    with a playbook, category_name and side_name; else "field value, …"."""
    if not m.group_label:
        return ", ".join(f"{k} {v}" for k, v in group_key.items()) or "All items"
    env = dict(group_key)
    if m.playbook:
        cat = m.playbook.categories.get(str(group_key.get("category")))
        side = str(group_key.get("side", ""))
        env.setdefault("category_name", cat.name if cat else group_key.get("category", ""))
        env.setdefault("side_name", m.playbook.side_names.get(side, side))
    try:
        return rules.render(m.group_label, env).strip() or "All items"
    except Exception:
        return ", ".join(f"{k} {v}" for k, v in group_key.items()) or "All items"


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
            label = group_label(m, group_key)
            total = round(sum(_num(it.get(m.items.amount_field)) for it in members), 2) \
                if m.items.amount_field else None
            priors = await knowledge.similar_decisions(
                state["capability_id"], group_key, exclude_case=state["case_id"],
                lookback_days=m.knowledge.priors_lookback_days,
                entities=knowledge.entity_values(m.knowledge.entities, group_key, members))
            g = {"group_id": group_id, "label": label, "group_key": group_key,
                 "item_ids": [it["item_id"] for it in members], "count": len(members),
                 "total": total, "priors": priors}
            groups.append(g)
            await s.merge(ProposalGroup(case_id=state["case_id"], group_id=group_id, label=label,
                                        group_key=group_key, item_ids=g["item_ids"],
                                        priors=priors, finding=None))
        await s.commit()
    return {"groups": groups}


async def reason_group(state: CaseState, g: dict, note: str | None = None,
                       previous: dict | None = None) -> dict:
    """One group's finding: the first matching rule, else the model (or an
    escalation when there is none). A reviewer's note forces the model."""
    m = _manifest(state)
    policy = m.policy_values()
    items = {it["item_id"]: it for it in state["items"]}
    members = [items[i] for i in g["item_ids"] if i in items]
    # carried: how many of the group's items were decided in the last run of
    # the series and are still here (follow_through).
    env = {**g["group_key"], "total": g["total"], "count": g["count"],
           "label": g["label"], "policy": policy,
           "carried": sum(1 for it in members if it.get("carried_verdict"))}
    play = _playbook_view(m, members, policy) if m.playbook else None
    with span("reason.group", case_id=state["case_id"], group_id=g["group_id"],
              reinvestigation=bool(note)) as sp:
        finding = None
        if play and play["deterministic"] and not note:
            finding = _playbook_finding(m, g, play, env)
        for rule in ([] if note or finding else m.rules):
            if rules.evaluate(rule.when, env):
                finding = {"status": rule.then.status, "decided_by": "rule", "rule": rule.id,
                           "comment": rules.render(rule.then.comment, env),
                           "reason": rule.then.reason}
                break
        if finding is None and m.reasoning.reasoner == "none":
            finding = {"status": ESCALATED, "decided_by": "none", "comment": "",
                       "reason": "NO_REASONER"}
            if play:
                finding.update(_play_fields(play))
        if finding is None and (over := await controls.over_budget(m, state["case_id"])):
            finding = {"status": ESCALATED, "decided_by": "none", "comment": "", "reason": over}
            if play:
                finding.update(_play_fields(play))
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
                allowed_tools=list(m.reasoning.tools), output=m.reasoning.output,
                reviewer_note=guard.scrub(note, [g["group_key"], *members]) if note else None,
                notes=[guard.scrub(text, [g["group_key"], *members]) for text in [
                    *(f"{n['by']} (tollgate before {n['step']}): {n['comment']}"
                      for n in state.get("gate_notes", []) if n.get("comment")),
                    *(f"context · {c['name']}: " + "; ".join(
                        ", ".join(f"{k}={v}" for k, v in r.items() if v not in (None, "")) for r in c["rows"][:40])
                      for c in state.get("model_context", [])),
                    *await asks.answers_for(state["case_id"], g["group_id"])]],
                previous_finding=guard.scrub(guard.protect(previous), [g["group_key"], *members])
                if previous else None,
                verdicts=m.playbook.verdict_names() if m.playbook else None,
                specialists=[sp.model_dump() for sp in m.reasoning.specialists],
                sections=[sec.model_dump() for sec in m.reasoning.sections])
            adapter = llm()
            try:
                res = await adapter.reason(request, gateway.invoker(ctx))
                finding = {"status": res.status, "decided_by": f"llm:{adapter.name}",
                           "comment": guard.reveal(res.comment),
                           "reason": guard.reveal(res.reason) if res.reason else None,
                           "model": res.model, "usage": res.usage}
                if m.reasoning.sections:
                    finding = _with_sections(m, finding, res, guard)
                if play:
                    finding = _judged(m, play, finding, res.verdict, env)
            except (gateway.ToolDenied, gateway.ToolFailed) as e:
                finding = {"status": ESCALATED, "decided_by": f"llm:{adapter.name}",
                           "comment": "", "reason": f"TOOL_ERROR: {e}"}
            except Exception as e:  # the model must never fail the run silently
                finding = {"status": ESCALATED, "decided_by": f"llm:{adapter.name}",
                           "comment": "", "reason": f"REASONER_ERROR: {type(e).__name__}: {e}"}
        from agent_one_finance import authority
        finding = authority.apply(m, {**g, "items_view": members}, finding, state.get("datasets") or {})
        sp.set_attribute("aof.decided_by", finding["decided_by"])
        sp.set_attribute("aof.status", finding["status"])
    return finding


def _with_sections(m: Manifest, finding: dict, res, guard) -> dict:
    """The answer's sections, in the configured order; a required one that is
    missing or empty sends the group to a person."""
    got = {k: guard.reveal(v).strip() for k, v in (res.sections or {}).items() if isinstance(v, str)}
    sections = [{"id": sec.id, "label": sec.label, "text": got.get(sec.id, "")} for sec in m.reasoning.sections]
    missing = [sec.label for sec in m.reasoning.sections if sec.required and not got.get(sec.id)]
    finding = {**finding, "sections": sections}
    if not finding.get("comment"):
        finding["comment"] = "\n\n".join(f"{x['label']}: {x['text']}" for x in sections if x["text"])
    if missing and finding["status"] == "proposed":
        finding.update(status=ESCALATED, reason=f"MISSING_SECTION: {', '.join(missing)}")
    return finding


def _playbook_view(m: Manifest, members: list[dict], policy: dict) -> dict:
    """What the playbook says about a group: its category and side when all its
    items agree, and whether the verdict table can settle it."""
    pb = m.playbook
    cats = {it.get("category") for it in members}
    sides = {it.get("side") for it in members}
    category = cats.pop() if len(cats) == 1 else None
    side = sides.pop() if len(sides) == 1 else None
    cat = pb.categories.get(category) if category else None
    unset = [p for p in pb.verdict_policy if policy.get(p) is None]
    return {"category": category, "side": side,
            "side_name": pb.side_names.get(side or "", side) if side else "Mixed sides",
            "category_name": cat.name if cat else "Mixed causes",
            "escalate_to": cat.escalate_to if cat else None,
            "determinism": cat.determinism if cat else "judgement",
            "deterministic": bool(cat and cat.determinism == "deterministic"
                                  and (cat.any_side or (side in pb.sides
                                                        and pb.verdicts.get(category, {}).get(side)))),
            "reasons": "; ".join(sorted({it.get("cause_reason", "") for it in members} - {""})),
            "unset_policy": unset,
            "blocked_by": sorted({b for it in members for b in it.get("blocked_by") or []})}


def _play_fields(play: dict) -> dict:
    return {k: play[k] for k in ("category", "category_name", "side", "side_name", "escalate_to", "determinism")
            if k in play}


def _guarded(m: Manifest, verdict: str | None, env: dict) -> tuple[str | None, str | None]:
    """Apply the playbook's guards: code, not the table or the model, has the last word."""
    for g in m.playbook.guards:
        if verdict == g.verdict and rules.evaluate(g.when, env):
            return g.instead, g.reason
    return verdict, None


def _with_verdict(m: Manifest, play: dict, finding: dict, verdict: str | None, env: dict) -> dict:
    pb = m.playbook
    verdict, guard_reason = _guarded(m, verdict, {**env, **_play_fields(play)})
    if verdict in pb.confirm_verdicts and play.get("blocked_by"):
        verdict = pb.blocked_verdict
        guard_reason = "Held: " + "; ".join(play["blocked_by"])
    out = {**finding, **_play_fields(play), "verdict": verdict}
    if play.get("blocked_by"):
        out["blocked_by"] = play["blocked_by"]
    if guard_reason:
        out["guard"] = guard_reason
    if verdict in pb.escalate_verdicts:
        out["status"] = ESCALATED
        out["reason"] = out.get("reason") or guard_reason or (
            f"Escalate to {play['escalate_to']}" if play["escalate_to"] else "ESCALATE")
    if verdict in pb.confirm_verdicts and play["unset_policy"]:
        out["requires_confirmation"] = (
            f"{verdict} depends on unset policy: {', '.join(play['unset_policy'])}")
    return out


def _playbook_finding(m: Manifest, g: dict, play: dict, env: dict) -> dict:
    table = m.playbook.verdicts[play["category"]]
    # any_side: one verdict for every side, so an unproven side takes it too
    verdict = table.get(play["side"]) or next(iter(table.values()))
    comment = rules.render(m.playbook.comment, {**env, **play})
    return _with_verdict(m, play, {"status": "proposed", "decided_by": "playbook",
                                   "comment": comment, "reason": None}, verdict, env)


def _judged(m: Manifest, play: dict, finding: dict, model_verdict: str | None, env: dict) -> dict:
    """A judgement call: the model investigated; its verdict (or the table's
    default for a proven side) still passes the guards, and a person decides."""
    table = m.playbook.verdicts.get(play["category"] or "", {})
    default = table.get(play["side"] or "")
    if default is None and len(set(table.values())) == 1:
        default = next(iter(table.values()))      # the same whichever side (e.g. ESCALATE)
    out = _with_verdict(m, play, finding, model_verdict or default, env)
    out["sme_review"] = True
    return out


def _concurrency(m: Manifest) -> int:
    """Groups reasoned at once. A capability with spend limits goes one at a
    time, so each group's budget check sees what the last one cost."""
    if m.limits.max_cost_usd_per_case is not None or m.limits.max_cost_usd_per_day is not None:
        return 1
    return max(1, int(os.getenv("AOF_REASON_CONCURRENCY") or 4))


async def reason(state: CaseState) -> dict:
    """Every group's finding — several groups at a time (each its own model
    session and gateway calls), saved as each one finishes."""
    gate = asyncio.Semaphore(_concurrency(_manifest(state)))

    async def one(g: dict) -> tuple[str, dict]:
        async with gate:
            finding = await reason_group(state, g)
            await _save_group_finding(state["case_id"], g["group_id"], finding)
            return g["group_id"], finding

    results = await asyncio.gather(*(one(g) for g in state["groups"]))
    return {"findings": dict(results)}


def _session_finding(m: Manifest, r: dict, adapter_name: str, model: str | None, guard) -> dict:
    """One result of a skill session as a finding: its verdict must be one the
    capability offers, an escalating verdict sends it to a person, and a
    required section that is missing does too."""
    rs = m.reasoning
    status = r.get("status") if r.get("status") in ("proposed", ESCALATED) else ESCALATED
    verdict = r.get("verdict") or None
    reason = guard.reveal(r["reason"]) if r.get("reason") else None
    if rs.verdicts and verdict not in rs.verdicts:
        status, reason = ESCALATED, f"NO_VALID_VERDICT: {verdict!r}"
        verdict = None
    elif verdict and verdict in rs.escalate_verdicts:
        status, reason = ESCALATED, reason or f"Verdict {verdict}"
    finding = {"status": status, "decided_by": f"llm:{adapter_name}", "comment": guard.reveal(r.get("comment") or ""),
               "reason": reason, "model": model}
    if verdict:
        finding["verdict"] = verdict
    if rs.sections:
        res = type("R", (), {"sections": r.get("sections") or {}})
        finding = _with_sections(m, finding, res, guard)
    return finding


def _merged(findings: list[dict], labels: list[str]) -> dict:
    """Several results in one group (group_by): one finding a person decides."""
    if len(findings) == 1:
        return findings[0]
    verdicts = {f.get("verdict") for f in findings}
    out = {"status": ESCALATED if any(f["status"] == ESCALATED for f in findings) else "proposed",
           "decided_by": findings[0]["decided_by"], "model": findings[0].get("model"),
           "comment": "\n".join(f"{lbl}: {f['comment']}" for lbl, f in zip(labels, findings) if f["comment"]),
           "reason": "; ".join(sorted({f["reason"] for f in findings if f.get("reason")})) or None}
    if len(verdicts) == 1 and None not in verdicts:
        out["verdict"] = verdicts.pop()
    return out


async def agent(state: CaseState) -> dict:
    """A skill session: the capability's skill, the case key and its allowed
    tools go to the model in ONE session. The model reads what it needs through
    the gateway (allow-list, book scope, masking, an audit row per call) and
    returns a result per item it investigated. Each result becomes an item and
    a finding; the gates that follow (validate, review, record) are the same as
    for any capability."""
    m = _manifest(state)
    rs = m.reasoning
    guard = Protector.for_tools(m.tools_used(), state["case_id"])
    ctx = _ctx(state, "agent", set(rs.tools))
    ctx.protector = guard
    adapter = llm()
    summary, results, model, usage = "", [], None, {}
    with span("agent.session", case_id=state["case_id"], tools=",".join(rs.tools)) as sp:
        failure = await controls.over_budget(m, state["case_id"])
        if failure is None:
            request = SessionRequest(
                capability_id=state["capability_id"], case_id=state["case_id"],
                case_key=guard.protect(state["case_key"]), skill=rs.skill, allowed_tools=list(rs.tools),
                id_field=m.items.id_field, item_label=m.case.item_label,
                amount_field=m.items.amount_field, result_fields=list(rs.result_fields),
                verdicts=list(rs.verdicts), sections=[x.model_dump() for x in rs.sections],
                specialists=[x.model_dump() for x in rs.specialists],
                notes=[f"{n['by']} (tollgate before {n['step']}): {n['comment']}"
                       for n in state.get("gate_notes", []) if n.get("comment")],
                max_turns=rs.max_turns)
            try:
                res = await run_session(adapter, request, gateway.invoker(ctx))
                summary, results, model, usage = guard.reveal(res.summary or ""), res.results, res.model, res.usage
            except (gateway.ToolDenied, gateway.ToolFailed) as e:
                failure = f"TOOL_ERROR: {e}"
            except Exception as e:  # the model must never fail the run silently
                failure = f"REASONER_ERROR: {type(e).__name__}: {e}"
        sp.set_attribute("aof.results", len(results))
    id_field = m.items.id_field
    items, found = [], []
    for r in results:
        rid = guard.reveal(str(r.get("id") or "")).strip() or f"result-{len(items) + 1}"
        fields = {k: (guard.reveal(v) if isinstance(v, str) else v) for k, v in (r.get("fields") or {}).items()}
        items.append({**fields, id_field: rid, "item_id": rid})
        found.append(_session_finding(m, r, adapter.name, model, guard))
    if failure or not results:
        # Nothing per item: the whole case is one group — escalated on a failure,
        # else the session's summary for a person to accept or send back.
        whole = {"status": ESCALATED if failure or not summary else "proposed",
                 "decided_by": f"llm:{adapter.name}", "comment": summary, "model": model,
                 "reason": failure or (None if summary else "NO_RESULTS")}
        buckets = {("all",): ([], [whole], ["Whole case"])}
    else:
        buckets = {}
        for it, f in zip(items, found):
            key = tuple(str(it.get(k)) for k in m.group_by) if m.group_by else (it["item_id"],)
            b = buckets.setdefault(key, ([], [], []))
            b[0].append(it)
            b[1].append(f)
            b[2].append(it["item_id"])
    if usage:
        next(iter(buckets.values()))[1][0]["usage"] = usage     # the session's cost, once
    await _save_items(state["case_id"], items)
    mask_f, pseudo_f = fields_for(m.tools_used())
    groups, findings = [], {}
    async with get_session() as s:
        for values, (members, fs, labels) in sorted(buckets.items()):
            fields_ = m.group_by or [id_field]
            group_key = dict(zip(fields_, values)) if values != ("all",) else {}
            group_id = _group_id(values, fields_, mask_f | pseudo_f) if group_key else "all"
            label = group_label(m, group_key) if m.group_by else (
                f"{m.case.item_label} {values[0]}" if group_key else "Whole case")
            total = round(sum(_num(it.get(m.items.amount_field)) for it in members), 2) \
                if m.items.amount_field and members else None
            finding = _merged(fs, labels)
            from agent_one_finance import authority
            finding = authority.apply(m, {"group_id": group_id, "group_key": group_key, "items_view": members,
                                          "total": total, "count": len(members), "label": label},
                                      finding, state.get("datasets") or {})
            priors = await knowledge.similar_decisions(
                state["capability_id"], group_key, exclude_case=state["case_id"],
                lookback_days=m.knowledge.priors_lookback_days,
                entities=knowledge.entity_values(m.knowledge.entities, group_key, members)) if group_key else []
            g = {"group_id": group_id, "label": label, "group_key": group_key,
                 "item_ids": [it["item_id"] for it in members], "count": len(members),
                 "total": total, "priors": priors}
            groups.append(g)
            findings[group_id] = finding
            await s.merge(ProposalGroup(case_id=state["case_id"], group_id=group_id, label=label,
                                        group_key=group_key, item_ids=g["item_ids"], priors=priors,
                                        finding=finding))
        await s.commit()
    return {"items": items, "groups": groups, "findings": findings, "session_summary": summary}


async def draft(state: CaseState) -> dict:
    m = _manifest(state)
    findings = state.get("findings", {})
    proposed = sum(1 for f in findings.values() if f["status"] == "proposed")
    escalated = sum(1 for f in findings.values() if f["status"] == ESCALATED)
    in_scope = sum(g["count"] for g in state["groups"])
    verdicts = Counter(f.get("verdict") for f in findings.values() if f.get("verdict"))
    d = {
        "headline": f"{in_scope} of {len(state['items'])} {m.case.item_label.lower()}(s) in scope, "
                    f"in {len(state['groups'])} group(s): {proposed} proposed, {escalated} escalated."
                    + (" Verdicts: " + ", ".join(f"{n} {v}" for v, n in sorted(verdicts.items())) + "."
                       if verdicts else ""),
        "groups": [{"group_id": g["group_id"], "label": g["label"],
                    "comment": findings.get(g["group_id"], {}).get("comment", "")}
                   for g in state["groups"]],
    }
    if m.items.amount_field:
        # Money at stake: the absolute amounts of the items in scope, to rank work by.
        in_ids = {i for g in state["groups"] for i in g["item_ids"]}
        d["exposure"] = round(sum(abs(_num(it.get(m.items.amount_field)))
                                  for it in state["items"] if it["item_id"] in in_ids), 2)
        d["unit"] = m.items.amount_unit
    if state.get("session_summary"):
        d["summary"] = state["session_summary"]     # the skill session's own words on the case
    if state.get("skipped"):
        d["skipped_steps"] = list(state["skipped"])    # steps whose `when` did not hold this run
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


def _session_run(state: CaseState) -> bool:
    return "agent" in (state.get("manifest") or {}).get("steps", [])


async def grounded_figures(state: CaseState) -> set[float]:
    """Every figure the run has read: the case key, its items and groups, and
    every allowed tool result recorded for the case. In a skill session the
    items are the model's own answer, so only the tools' results count."""
    grounded: set[float] = set()
    own = [] if _session_run(state) else [state["items"], state["groups"]]
    _numbers_in([state["case_key"], *own, state.get("datasets") or {}], grounded)
    async with get_session() as s:
        results = (await s.execute(select(ToolCall.result).where(
            ToolCall.case_id == state["case_id"], ToolCall.allowed.is_(True),
            ToolCall.result.is_not(None)))).scalars().all()
    _numbers_in(list(results), grounded)
    return grounded


def ungrounded(text: str, grounded: set[float]) -> list[float]:
    cited = {round(float(n.replace(",", "")), 2) for n in _NUMBER.findall(text or "")}
    return sorted(n for n in cited if n not in grounded)


async def validate(state: CaseState) -> dict:
    """Gate: every figure in a proposed finding must trace to data the run read."""
    grounded = await grounded_figures(state)

    findings = dict(state.get("findings", {}))
    groups_by_id = {g["group_id"]: g for g in state.get("groups", [])}
    errors = []
    for group_id, f in findings.items():
        if f["status"] != "proposed":
            continue
        text = " ".join([f["comment"], *(x.get("text", "") for x in f.get("sections") or [])])
        missing = ungrounded(text, grounded)
        if _session_run(state):
            # the figures a session put on its results (e.g. a break's difference) are checked too
            members = set(groups_by_id.get(group_id, {}).get("item_ids", []))
            cited = {round(abs(float(v)), 2) for it in state.get("items", []) if it["item_id"] in members
                     for v in it.values() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            missing = sorted(set(missing) | {n for n in cited if n not in grounded})
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
    m = _manifest(state)
    findings = state.get("findings", {})
    groups = {g["group_id"]: g for g in state["groups"]}
    items = {it["item_id"]: it for it in state.get("items", [])}
    for d in state.get("decisions", []):
        g = groups.get(d["group_id"])
        if g is None:
            continue
        await knowledge.record_decision(
            state["capability_id"], g["group_key"], case_id=state["case_id"],
            group_id=d["group_id"], action=d["action"],
            comment=d.get("comment") or findings.get(d["group_id"], {}).get("comment", ""),
            decided_by=d["decided_by"],
            entities=knowledge.entity_values(
                m.knowledge.entities, g["group_key"],
                [items[i] for i in g["item_ids"] if i in items]))
    if m.escalation:
        from agent_one_finance import escalation
        ctx = _ctx(state, "escalate", {m.escalation.tool})
        ctx.escalation_tool = m.escalation.tool
        await escalation.raise_tickets(m, state, ctx)
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


def publish_calls(state: CaseState) -> list[tuple[str, dict]]:
    """(idempotency key, arguments) for every write the case's publish makes:
    one per approved group, or one for the whole case."""
    m = _manifest(state)
    approval = state.get("publish_approval") or {}
    approved = _approved(state, m)
    common = {"$case_id": state["case_id"], "$subject": _subject(m, state["case_key"])}
    if m.publish.per == "case":
        if not approved:
            return []
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
        return [(f"{state['case_id']}:case", _publish_args(m.publish.args, state, {
            **common, "$approved": sections, "$sign_off": sign_off}))]
    return [(f"{state['case_id']}:{g['group_id']}", _publish_args(m.publish.args, state, {
                **common, "$group": g["group_key"], "$comment": comment}))
            for g, _, comment in approved]


async def write_back(state: CaseState, released_by: str | None,
                     done: frozenset[str] = frozenset()) -> tuple[list[dict], list[str]]:
    """Make the publish writes, skipping those already made (`done` keys).
    Every write carries its idempotency key, so a repeat is the same write."""
    m = _manifest(state)
    ctx = _ctx(state, "publish", {m.publish.tool})
    ctx.requested_by, ctx.write_approved_by = "publish", released_by
    published, failed = [], []
    for key, args in publish_calls(state):
        if key in done:
            continue
        try:
            receipt = await gateway.call(ctx, m.publish.tool, args, idempotency_key=key)
            published.append({"key": key, "receipt": receipt})
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            failed.append(f"{key.split(':', 1)[1]}: {e}")
    return published, failed


async def set_publish_outcome(case_id: str, failed: list[str]) -> str:
    outcome = "published" if not failed else "publish_failed"
    async with get_session() as s:
        case = await s.get(Case, case_id)
        case.status, case.outcome = ("completed", outcome) if not failed else ("failed", outcome)
        case.error = "; ".join(failed) or None
        await s.commit()
    return outcome


async def publish(state: CaseState) -> dict:
    """Write the approved results back through the capability's write tool —
    one call per approved group, or one for the whole case (a report).
    Runs only after a second person released it (publish_approval)."""
    approval = state.get("publish_approval") or {}
    published, failed = await write_back(state, approval.get("approved_by"))
    outcome = await set_publish_outcome(state["case_id"], failed)
    return {"outcome": outcome, "published": published}


async def escalate(state: CaseState) -> dict:
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        case.status, case.outcome, case.error = ESCALATED, ESCALATED, state.get("escalation_reason")
        await s.commit()
    return {}
