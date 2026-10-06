"""Steps v2, phases 2–6: generic step types for case-based work in Finance and beyond.

Registered with the step SDK (agent_one_finance/stepkit.py), configured under
`step_settings`, checked with the manifest, run under the same gateway, audit
and controls as every other step:

  accounting actions  recompute, schedule, propose_entries, period_check, post
  assurance           flux, anomaly, consistency, sample, score, attest
  orchestration       await, spawn, report, compose
  acquisition         match_n, intake, extract
  time, context and   clock, timeline, link, screen, outreach
  parties

No type holds a team's logic: thresholds are policy, logic is expressions, and
anything else is a team's own tool behind the gateway. Nothing a step removes
is lost; nothing writes without a person's approval; the model never makes a
decision a capability reserves for people (agent_one_finance/authority.py).
"""

import difflib
import hashlib
import random
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import Field

from agent_one_finance import rules
from agent_one_finance.stepkit import (Cfg, StepType, _args, _ctx, _env, _exclude, _keep_dataset, _save, ds,
                           register)


def _steps():
    from agent_one_finance import steps
    return steps


def _m(state):
    return _steps()._manifest(state)


def _group_env(state, g: dict, finding: dict | None = None) -> dict:
    f = finding or (state.get("findings") or {}).get(g["group_id"], {}) or {}
    return {**g.get("group_key", {}), "total": g.get("total"), "count": g.get("count"), "label": g.get("label"),
            "verdict": f.get("verdict"), "status": f.get("status"), "category": f.get("category"),
            "comment": f.get("comment", ""), "policy": _m(state).policy_values(), "case": dict(state["case_key"]),
            **{f"case_{k}": v for k, v in state["case_key"].items()}}


def _render(template: str, env: dict) -> str:
    return rules.render(template, env)


def _value(spec: Any, item: dict, case_key: dict) -> Any:
    """A setting's value: literal, $case.<field> or $item.<field>."""
    if isinstance(spec, str) and spec.startswith("$case."):
        return case_key.get(spec[6:])
    if isinstance(spec, str) and spec.startswith("$item."):
        return item.get(spec[6:])
    return spec


async def _call(state, step_id: str, tool: str, args: dict, *, write_by: str | None = None) -> dict:
    from agent_one_finance import gateway
    ctx = _ctx(state, step_id, {tool})
    if write_by:
        ctx.write_approved_by = write_by
        ctx.write_tools = frozenset({tool})
    return await gateway.call(ctx, tool, args)


def _failed(reason: str, e: Exception) -> dict:
    return _steps()._escalate(reason, str(e))


# =====================================================================
# Phase 2 — accounting actions
# =====================================================================

class RecomputeCfg(Cfg):
    formula: str | None = None        # expression over the item, case and policy
    tool: str | None = None           # …or a tool returning rows {item_id, value}
    args: dict[str, Any] = Field(default_factory=dict)
    compare_to: str                   # the booked figure
    as_: str = Field(default="recomputed", alias="as")
    tolerance: float = 0.01


async def _recompute(state, cfg: RecomputeCfg, step_id):
    values: dict[str, Any] = {}
    if cfg.tool:
        from agent_one_finance import gateway
        try:
            res = await _call(state, step_id, cfg.tool, {**_args(cfg.args, state["case_key"]),
                                                         "items": [{"item_id": i["item_id"], **i} for i in state["items"]]})
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            return _failed("RECOMPUTE_FAILED", e)
        values = {str(r.get("item_id")): r.get("value") for r in res.get("rows", [])}
    items = []
    for it in state["items"]:
        new = dict(it)
        try:
            v = values.get(it["item_id"]) if cfg.tool else rules.evaluate(cfg.formula, _env(state, it))
            v = round(float(v), 2) if v is not None else None
        except Exception as e:
            v = None
            new["recompute_error"] = str(e)
        booked = it.get(cfg.compare_to)
        new[cfg.as_] = v
        if v is not None and booked is not None:
            diff = round(v - float(booked), 2)
            new[f"{cfg.as_}_difference"] = diff
            new[f"{cfg.as_}_ok"] = abs(diff) <= cfg.tolerance
        else:
            new[f"{cfg.as_}_ok"] = None          # could not tell: never assumed right
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "recompute", "Recompute and compare", "Recalculates a figure (fees, interest, accruals) by formula or the team's tool and compares it to what was booked.",
    RecomputeCfg, _recompute, tools=lambda c: {c.tool} if c.tool else set(),
    expressions=lambda c: [("formula", c.formula)] if c.formula else []))


class ScheduleCfg(Cfg):
    amount: str                       # item field
    periods: int = Field(ge=1, le=600)
    start: str                        # item field or $case.<field>: the first period (YYYY-MM or a date)
    into: str = "schedule"


def _months(start: str, n: int) -> list[str]:
    y, mth = int(str(start)[:4]), int(str(start)[5:7])
    out = []
    for i in range(n):
        yy, mm = y + (mth - 1 + i) // 12, (mth - 1 + i) % 12 + 1
        out.append(f"{yy:04d}-{mm:02d}")
    return out


async def _schedule(state, cfg: ScheduleCfg, step_id):
    rows = []
    for it in state["items"]:
        total = it.get(cfg.amount)
        start = _value(cfg.start if cfg.start.startswith("$") else f"$item.{cfg.start}", it, state["case_key"])
        if total is None or not start:
            continue
        each = round(float(total) / cfg.periods, 2)
        months = _months(str(start), cfg.periods)
        for i, p in enumerate(months):
            amt = each if i < cfg.periods - 1 else round(float(total) - each * (cfg.periods - 1), 2)
            rows.append({"item_id": it["item_id"], "period": p, "amount": amt, "method": "straight_line"})
    await _keep_dataset(state, step_id, cfg.into, step_id, rows)
    return {"datasets": {**(state.get("datasets") or {}), cfg.into: rows}}


register(StepType(
    "schedule", "Schedule over periods", "Spreads each item's amount over periods (prepayments, accrual release, leases) into a data set.",
    ScheduleCfg, _schedule, produces=lambda c: {ds(c.into)}))


class EntryLine(Cfg):
    account: str                       # template over the group, e.g. "{account}" or "2100"
    side: Literal["debit", "credit"]
    amount: str = "abs(total)"         # expression over the group
    cost_centre: str = ""
    narrative: str = "{label}"


class ProposeEntriesCfg(Cfg):
    when: str = "status == 'proposed'"   # which groups get entries (expression over the group)
    lines: list[EntryLine] = Field(min_length=2)
    period: str = "$case.period"
    chart: str | None = None             # data set of valid accounts (rows with `account`)
    into: str = "journals"


async def _propose_entries(state, cfg: ProposeEntriesCfg, step_id):
    s = _steps()
    findings = dict(state.get("findings") or {})
    chart = {str(r.get("account")) for r in (state.get("datasets") or {}).get(cfg.chart, [])} if cfg.chart else None
    period = _value(cfg.period, {}, state["case_key"])
    journals = []
    for g in state.get("groups") or []:
        f = dict(findings.get(g["group_id"]) or {})
        env = _group_env(state, g, f)
        try:
            if not rules.evaluate(cfg.when, env):
                continue
        except rules.ExpressionError:
            continue
        lines, problems = [], []
        for ln in cfg.lines:
            try:
                amt = round(float(rules.evaluate(ln.amount, env)), 2)
            except Exception as e:
                problems.append(f"amount for {ln.account}: {e}")
                continue
            acct = _render(ln.account, env)
            if chart is not None and acct not in chart:
                problems.append(f"account {acct} is not in the chart of accounts")
            lines.append({"account": acct, "side": ln.side, "amount": amt,
                          "cost_centre": _render(ln.cost_centre, env), "narrative": _render(ln.narrative, env)})
        dr = round(sum(x["amount"] for x in lines if x["side"] == "debit"), 2)
        cr = round(sum(x["amount"] for x in lines if x["side"] == "credit"), 2)
        if dr != cr:
            problems.append(f"unbalanced: debits {dr:,.2f} ≠ credits {cr:,.2f}")
        if not period:
            problems.append("no accounting period")
        jid = "JE-" + hashlib.sha1(f"{state['case_id']}|{g['group_id']}".encode()).hexdigest()[:10]
        entry = {"journal_id": jid, "period": period, "lines": lines, "debits": dr, "credits": cr,
                 "balanced": dr == cr, "problems": problems}
        f["entries"] = entry
        if problems and f.get("status") == "proposed":
            f.update(status="escalated", reason="ENTRY_INVALID: " + "; ".join(problems))
        findings[g["group_id"]] = f
        await s._save_group_finding(state["case_id"], g["group_id"], f)
        journals.append({"group_id": g["group_id"], **{k: v for k, v in entry.items() if k != "lines"},
                         "lines": len(lines)})
    await _keep_dataset(state, step_id, cfg.into, step_id, journals)
    return {"findings": findings, "datasets": {**(state.get("datasets") or {}), cfg.into: journals}}


register(StepType(
    "propose_entries", "Journal entries", "Drafts balanced journals for the groups that need them; an unbalanced entry, an unknown account or no period is caught before anyone sees it.",
    ProposeEntriesCfg, _propose_entries,
    needs=lambda c: {"groups", "findings"} | ({ds(c.chart)} if c.chart else set()),
    produces=lambda c: {"findings", ds(c.into)},
    expressions=lambda c: [("when", c.when), *[(f"lines[{i}].amount", ln.amount) for i, ln in enumerate(c.lines)]],
    dataset_refs=lambda c: {c.chart} if c.chart else set()))


class PeriodCheckCfg(Cfg):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    status_field: str = "status"
    open_values: list[str] = Field(default_factory=lambda: ["open"])


async def _period_check(state, cfg: PeriodCheckCfg, step_id):
    from agent_one_finance import gateway
    try:
        res = await _call(state, step_id, cfg.tool, _args(cfg.args, state["case_key"]))
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return _failed("PERIOD_CHECK_FAILED", e)
    rows = res.get("rows", [])
    await _keep_dataset(state, step_id, "period", cfg.tool, rows)
    status = str((rows[0] if rows else {}).get(cfg.status_field, "unknown"))
    if status not in cfg.open_values:
        return _steps()._escalate("PERIOD_CLOSED", f"the accounting period is {status}")
    return {}


register(StepType(
    "period_check", "Period open?", "Stops the run (to a person) if the accounting period is closed or locked for the entity.",
    PeriodCheckCfg, _period_check, needs=lambda c: set(), produces=lambda c: set(), tools=lambda c: {c.tool}))


class PostCfg(Cfg):
    tool: str                          # the ledger's write tool
    dry_run_tool: str | None = None    # the ledger's validation (read) tool, called first
    args: dict[str, Any] = Field(default_factory=dict)
    approver_roles: list[str] = Field(min_length=1)


async def _post(state, cfg: PostCfg, step_id):
    from agent_one_finance import gateway
    approval = state.get("publish_approval") or {}
    approved = {d["group_id"] for d in state.get("decisions", []) if d.get("action") == "approve"}
    rows = []
    for gid, f in (state.get("findings") or {}).items():
        e = (f or {}).get("entries")
        if gid not in approved or not e or not e.get("balanced") or e.get("problems"):
            continue
        payload = {**_args(cfg.args, state["case_key"]), "journal_id": e["journal_id"], "period": e["period"],
                   "lines": e["lines"]}
        row = {"group_id": gid, "journal_id": e["journal_id"]}
        try:
            if cfg.dry_run_tool:
                check = await _call(state, step_id, cfg.dry_run_tool, payload)
                if not check.get("ok", True):
                    row.update(status="rejected by the ledger", errors=check.get("errors", []))
                    rows.append(row)
                    continue
            res = await _call(state, step_id, cfg.tool, {**payload, "idempotency_key": f"{state['case_id']}:{e['journal_id']}"},
                              write_by=approval.get("approved_by") or "release")
            row.update(status="posted", reference=res.get("reference"))
        except (gateway.ToolDenied, gateway.ToolFailed) as ex:
            row.update(status="failed", error=str(ex))
        rows.append(row)
    await _keep_dataset(state, step_id, "posted", cfg.tool, rows)
    failed = [r for r in rows if r["status"] != "posted"]
    from agent_one_finance.db import get_session
    from agent_one_finance.models import Case
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        case.status, case.outcome = ("failed", "post_failed") if failed else ("completed", "posted")
        case.error = "; ".join(f"{r['journal_id']}: {r.get('error') or r['status']}" for r in failed) or None
        await s.commit()
    return {"outcome": "post_failed" if failed else "posted",
            "datasets": {**(state.get("datasets") or {}), "posted": rows}}


register(StepType(
    "post", "Post journals", "Posts the approved journals to the ledger after a second person releases them — the ledger's own check first; each journal once, however often retried.",
    PostCfg, _post, needs=lambda c: {"decisions", "findings"}, produces=lambda c: {"outcome"},
    tools=lambda c: {c.tool} | ({c.dry_run_tool} if c.dry_run_tool else set()),
    extra={"writes": lambda c: {c.tool}}))


# =====================================================================
# Phase 3 — assurance
# =====================================================================

class HistoryCfg(Cfg):
    history: str                      # data set of past values
    key: str                          # the field on both the items and the history
    value: str                        # the item's figure
    history_value: str = "value"


def _series(state, cfg) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in (state.get("datasets") or {}).get(cfg.history, []):
        v = r.get(cfg.history_value)
        if isinstance(v, (int, float)):
            out.setdefault(str(r.get(cfg.key)), []).append(float(v))
    return out


class FluxCfg(HistoryCfg):
    prefix: str = "flux"


async def _flux(state, cfg: FluxCfg, step_id):
    hist = _series(state, cfg)
    items = []
    for it in state["items"]:
        new, past, v = dict(it), hist.get(str(it.get(cfg.key)), []), it.get(cfg.value)
        if past and isinstance(v, (int, float)):
            mean = statistics.fmean(past)
            sd = statistics.pstdev(past) if len(past) > 1 else 0.0
            new[f"{cfg.prefix}_baseline"] = round(mean, 2)
            new[f"{cfg.prefix}_change"] = round(v - mean, 2)
            new[f"{cfg.prefix}_pct"] = round((v - mean) / abs(mean) * 100, 1) if mean else None
            new[f"{cfg.prefix}_z"] = round((v - mean) / sd, 2) if sd else None
        else:
            new[f"{cfg.prefix}_change"] = None      # no history: shown, never zero
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "flux", "Change over periods", "Compares each item with its own history: change, % change and how unusual (z-score).",
    FluxCfg, _flux, needs=lambda c: {"items", ds(c.history)}, dataset_refs=lambda c: {c.history}))


class AnomalyCfg(HistoryCfg):
    threshold: float = 3.0


async def _anomaly(state, cfg: AnomalyCfg, step_id):
    hist = _series(state, cfg)
    items = []
    for it in state["items"]:
        new, past, v = dict(it), hist.get(str(it.get(cfg.key)), []), it.get(cfg.value)
        z = None
        if len(past) > 1 and isinstance(v, (int, float)) and statistics.pstdev(past):
            z = (v - statistics.fmean(past)) / statistics.pstdev(past)
        new["anomaly_z"] = round(z, 2) if z is not None else None
        new["anomaly"] = bool(z is not None and abs(z) >= cfg.threshold)
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "anomaly", "Unusual against history", "Flags items far from their own history (z-score above a threshold) — statistics, no model.",
    AnomalyCfg, _anomaly, needs=lambda c: {"items", ds(c.history)}, dataset_refs=lambda c: {c.history}))


class Side(Cfg):
    source: str = "items"             # items or a data set
    field: str
    where: str | None = None


class Check(Cfg):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,40}$")
    left: Side
    right: Side
    tolerance: float = 0.01
    message: str = ""


class ConsistencyCfg(Cfg):
    checks: list[Check] = Field(min_length=1)


def _total(state, side: Side) -> float:
    rows = state["items"] if side.source == "items" else (state.get("datasets") or {}).get(side.source, [])
    total = 0.0
    for r in rows:
        if side.where:
            try:
                if not rules.evaluate(side.where, {**r, "case": dict(state["case_key"])}):
                    continue
            except rules.ExpressionError:
                continue
        v = r.get(side.field)
        if isinstance(v, (int, float)):
            total += v
    return round(total, 2)


async def _consistency(state, cfg: ConsistencyCfg, step_id):
    out = []
    for c in cfg.checks:
        a, b = _total(state, c.left), _total(state, c.right)
        if abs(a - b) > c.tolerance:
            out.append({"item_id": f"check:{c.id}", "check": c.id, "left_total": a, "right_total": b,
                        "difference": round(a - b, 2),
                        "message": c.message or f"{c.left.source}.{c.left.field} ≠ {c.right.source}.{c.right.field}"})
    await _save(state, out)
    return {"items": [*state["items"], *out]}


register(StepType(
    "consistency", "Consistency checks", "Checks totals across data sets (sub-ledger = GL, report A = report B); each failing check becomes an item to investigate.",
    ConsistencyCfg, _consistency,
    needs=lambda c: {"items"} | {ds(s.source) for ch in c.checks for s in (ch.left, ch.right) if s.source != "items"},
    expressions=lambda c: [(f"checks[{ch.id}].{n}.where", s.where) for ch in c.checks
                           for n, s in (("left", ch.left), ("right", ch.right)) if s.where],
    dataset_refs=lambda c: {s.source for ch in c.checks for s in (ch.left, ch.right) if s.source != "items"}))


class SampleCfg(Cfg):
    method: Literal["random", "top", "monetary"] = "random"
    size: int | None = Field(default=None, ge=1)
    percent: float | None = Field(default=None, gt=0, le=100)
    field: str | None = None              # for top and monetary
    stratify_by: str | None = None
    always_include_when: str | None = None


async def _sample(state, cfg: SampleCfg, step_id):
    items = state["items"]
    seed = int(hashlib.sha256(f"{state['case_id']}|{step_id}".encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    forced = []
    if cfg.always_include_when:
        for it in items:
            try:
                if rules.evaluate(cfg.always_include_when, _env(state, it)):
                    forced.append(it)
            except rules.ExpressionError:
                forced.append(it)
    forced_ids = {i["item_id"] for i in forced}
    pool = [i for i in items if i["item_id"] not in forced_ids]

    def n_for(group: list) -> int:
        if cfg.size:
            return min(len(group), cfg.size if not cfg.stratify_by else max(1, round(cfg.size * len(group) / max(1, len(pool)))))
        return min(len(group), max(1, round(len(group) * (cfg.percent or 10) / 100)))

    strata: dict[str, list] = {}
    for it in pool:
        strata.setdefault(str(it.get(cfg.stratify_by)) if cfg.stratify_by else "all", []).append(it)
    chosen = []
    for _, group in sorted(strata.items()):
        n = n_for(group)
        if cfg.method == "top" and cfg.field:
            chosen += sorted(group, key=lambda i: -abs(float(i.get(cfg.field) or 0)))[:n]
        elif cfg.method == "monetary" and cfg.field:
            weights = [abs(float(i.get(cfg.field) or 0)) + 1e-9 for i in group]
            picked: list = []
            g, w = list(group), list(weights)
            while g and len(picked) < n:
                k = rng.choices(range(len(g)), weights=w)[0]
                picked.append(g.pop(k))
                w.pop(k)
            chosen += picked
        else:
            chosen += rng.sample(group, n)
    keep_ids = forced_ids | {i["item_id"] for i in chosen}
    keep = [{**i, "sampled": "always" if i["item_id"] in forced_ids else cfg.method} for i in items if i["item_id"] in keep_ids]
    await _exclude(state, step_id, [i for i in items if i["item_id"] not in keep_ids], "not in the sample")
    await _save(state, keep)
    log = [{"seed": seed, "method": cfg.method, "population": len(items), "selected": len(keep),
            "always_included": len(forced), "stratify_by": cfg.stratify_by}]
    await _keep_dataset(state, step_id, "sample", step_id, log)
    return {"items": keep, "datasets": {**(state.get("datasets") or {}), "sample": log}}


register(StepType(
    "sample", "Sample", "Selects a reproducible sample (random, largest, or by value; stratified; some always included); the rest stay on the case, marked.",
    SampleCfg, _sample, expressions=lambda c: [("always_include_when", c.always_include_when)] if c.always_include_when else []))


class Factor(Cfg):
    when: str
    weight: float
    label: str


class ScoreBand(Cfg):
    label: str
    upto: float | None = None


class ScoreCfg(Cfg):
    factors: list[Factor] = Field(min_length=1)
    as_: str = Field(default="score", alias="as")
    bands: list[ScoreBand] = Field(default_factory=list)
    band_as: str = "band"


async def _score(state, cfg: ScoreCfg, step_id):
    items = []
    for it in state["items"]:
        total, why = 0.0, []
        for f in cfg.factors:
            try:
                if rules.evaluate(f.when, _env(state, it)):
                    total += f.weight
                    why.append(f.label)
            except rules.ExpressionError:
                pass
        new = {**it, cfg.as_: round(total, 2), f"{cfg.as_}_reasons": why}
        if cfg.bands:
            new[cfg.band_as] = next((b.label for b in cfg.bands if b.upto is None or total <= b.upto), cfg.bands[-1].label)
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "score", "Risk score", "Adds a weighted score from named factors, its reasons and a band (high / medium / low) that review lanes and approvals can use.",
    ScoreCfg, _score, expressions=lambda c: [(f"factors[{f.label}].when", f.when) for f in c.factors]))


class AttestCfg(Cfg):
    statement: str
    roles: list[str] = Field(min_length=1)
    evidence_required: bool = False
    valid_for_days: int | None = Field(default=None, ge=1)


async def _attest(state, cfg: AttestCfg, step_id):
    """Runs once a person passed the tollgate before it (they read the
    statement there); records the attestation, and needs evidence if asked."""
    from sqlalchemy import func, select

    from agent_one_finance.db import get_session
    from agent_one_finance.models import Document
    note = next((n for n in reversed(state.get("gate_notes") or []) if n.get("step") == step_id), {})
    async with get_session() as s:
        evidence = (await s.execute(select(func.count()).select_from(Document).where(
            Document.case_id == state["case_id"], Document.kind == "evidence"))).scalar_one()
    if cfg.evidence_required and not evidence:
        return _steps()._escalate("NO_EVIDENCE", f"`{step_id}` needs evidence on the case before it is attested")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = {"statement": cfg.statement, "by": note.get("by"), "comment": note.get("comment"),
           "at": now.isoformat(timespec="seconds") + "Z", "evidence_files": evidence,
           "valid_until": (now + timedelta(days=cfg.valid_for_days)).date().isoformat() if cfg.valid_for_days else None}
    rows = [*((state.get("datasets") or {}).get("attestations", [])), row]
    await _keep_dataset(state, step_id, "attestations", step_id, rows)
    return {"datasets": {**(state.get("datasets") or {}), "attestations": rows}}


register(StepType(
    "attest", "Owner attestation", "An owner certifies a statement (an account, a control, a report) at a tollgate; recorded with who, when, evidence and expiry.",
    AttestCfg, _attest, needs=lambda c: set(), produces=lambda c: set(), extra={"person": True}))


# =====================================================================
# Phase 4 — orchestration
# =====================================================================

class AwaitCfg(Cfg):
    # The event's name; `children` = the child cases a `spawn` opened, all finished.
    event: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    timeout_hours: float | None = Field(default=None, gt=0)
    on_timeout: Literal["continue", "escalate"] = "escalate"
    # Who may deliver the event by hand (besides a system with the event secret).
    roles: list[str] = Field(default_factory=list)


async def _await(state, cfg: AwaitCfg, step_id):
    payload = (state.get("events") or {}).get(step_id) or {}
    rows = [{"event": cfg.event, **{k: v for k, v in payload.items() if k != "children"}}]
    await _keep_dataset(state, step_id, f"event_{step_id}", cfg.event, rows)
    if payload.get("timed_out") and cfg.on_timeout == "escalate":
        return _steps()._escalate("TIMED_OUT", f"no `{cfg.event}` within {cfg.timeout_hours:g} hours")
    if cfg.event == "children":
        kids = payload.get("children") or {}
        spawned = {r["child_case_id"]: r for r in (state.get("datasets") or {}).get("children", [])}
        by_item = {r["item_id"]: r["child_case_id"] for r in spawned.values()}
        items = [{**it, "child_case_id": by_item.get(it["item_id"]),
                  "child_status": (kids.get(by_item.get(it["item_id"]), {}) or {}).get("status"),
                  "child_outcome": (kids.get(by_item.get(it["item_id"]), {}) or {}).get("outcome")} for it in state["items"]]
        await _save(state, items)
        return {"items": items}
    return {}


register(StepType(
    "await", "Wait for an event", "The run waits here for an event (a reply, a confirmation, a file) or for its child cases, with a timeout.",
    AwaitCfg, _await, needs=lambda c: {"children"} if c.event == "children" else set(),
    produces=lambda c: set(), extra={"wait": True}))


class SpawnCfg(Cfg):
    capability: str
    team_group: str | None = None
    key: dict[str, str]                # child case key: $item.<field>, $case.<field> or a literal
    max_children: int = Field(default=200, ge=1, le=2000)


async def _spawn(state, cfg: SpawnCfg, step_id):
    from agent_one_finance import cases
    caller = _steps()._caller(state)
    rows = []
    for it in state["items"][: cfg.max_children]:
        key = {k: _value(v, it, state["case_key"]) for k, v in cfg.key.items()}
        try:
            cid = await cases.open_case(cfg.capability, key, caller, cfg.team_group, parent=state["case_id"])
        except Exception as e:          # one child that cannot open is visible, not fatal
            rows.append({"item_id": it["item_id"], "child_case_id": None, "error": str(e)})
            continue
        rows.append({"item_id": it["item_id"], "child_case_id": cid, "key": key})
    await _keep_dataset(state, step_id, "children", cfg.capability, rows)
    return {"datasets": {**(state.get("datasets") or {}), "children": rows}, "spawned": True}


register(StepType(
    "spawn", "Child cases", "Opens a child case per item (per account, per sample, per client) in a capability; an `await` for `children` then rolls their outcomes up.",
    SpawnCfg, _spawn, produces=lambda c: {"children"}))


class ReportCfg(Cfg):
    name: str = "case-report"


async def _report(state, cfg: ReportCfg, step_id):
    """The case's evidence pack (configuration, findings, decisions, data used),
    kept as one of its documents."""
    import hashlib as h

    from agent_one_finance import evidence
    from agent_one_finance.db import get_session
    from agent_one_finance.models import Document
    caller = _steps()._caller(state)
    content, _ = await evidence.pack(state["case_id"], caller)
    name = f"{state['case_id']}--{cfg.name}.pdf"
    async with get_session() as s:
        await s.merge(Document(scope=str(next(iter(state["case_key"].values()))), name=name, content=content,
                               content_type="application/pdf", sha256=h.sha256(content).hexdigest(),
                               kind="report", case_id=state["case_id"], uploaded_by="aof"))
        await s.commit()
    return {}


register(StepType(
    "report", "Report", "Writes the case's report (configuration, findings, decisions, data used, sign-off) as a PDF kept with the case.",
    ReportCfg, _report, needs=lambda c: {"decisions"}, produces=lambda c: set()))


class ComposeCfg(Cfg):
    when: str = "status == 'proposed'"
    to: str                           # template over the group, e.g. "{counterparty_bic}"
    subject: str
    body: str


async def _compose(state, cfg: ComposeCfg, step_id):
    s = _steps()
    findings = dict(state.get("findings") or {})
    for g in state.get("groups") or []:
        f = dict(findings.get(g["group_id"]) or {})
        env = {**_group_env(state, g, f), "comment": f.get("comment", "")}
        try:
            if not rules.evaluate(cfg.when, env):
                continue
        except rules.ExpressionError:
            continue
        f["draft_message"] = {"to": _render(cfg.to, env), "subject": _render(cfg.subject, env),
                              "body": _render(cfg.body, env), "step": step_id}
        findings[g["group_id"]] = f
        await s._save_group_finding(state["case_id"], g["group_id"], f)
    return {"findings": findings}


register(StepType(
    "compose", "Draft a message", "Drafts the outbound message per group (client reply, counterparty query) for the reviewer; it is sent only by an approved `outreach` or write-back.",
    ComposeCfg, _compose, needs=lambda c: {"groups", "findings"}, produces=lambda c: {"findings"},
    expressions=lambda c: [("when", c.when)]))


# =====================================================================
# Phase 5 — acquisition
# =====================================================================

class Source(Cfg):
    label: str = Field(pattern=r"^[a-z][a-z0-9_]{0,20}$")
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    amount_field: str = "amount"


class MatchNCfg(Cfg):
    sources: list[Source] = Field(min_length=2, max_length=6)
    keys: list[str] = Field(min_length=1)
    tolerance: float = 0.01
    many_to_one: bool = True          # sum each source's rows per key before comparing


async def _match_n(state, cfg: MatchNCfg, step_id):
    from agent_one_finance import gateway
    sides: dict[str, dict[tuple, dict]] = {}
    for src in cfg.sources:
        try:
            rows = (await _call(state, step_id, src.tool, _args(src.args, state["case_key"]))).get("rows", [])
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            return _failed("LOAD_FAILED", e)
        agg: dict[tuple, dict] = {}
        for r in rows:
            k = tuple(str(r.get(f)) for f in cfg.keys)
            if k in agg and cfg.many_to_one:
                agg[k]["amount"] += float(r.get(src.amount_field) or 0)
                agg[k]["rows"] += 1
            else:
                agg[k] = {"amount": float(r.get(src.amount_field) or 0), "rows": 1, "row": r}
        sides[src.label] = agg
    items = []
    for k in sorted(set().union(*[set(v) for v in sides.values()])):
        present = {lab: v[k] for lab, v in sides.items() if k in v}
        amounts = [p["amount"] for p in present.values()]
        missing = [lab for lab in sides if lab not in present]
        if not missing and max(amounts) - min(amounts) <= cfg.tolerance:
            continue
        base = next(iter(present.values()))["row"]
        items.append({"item_id": "|".join(k), **dict(zip(cfg.keys, [base.get(f) for f in cfg.keys])),
                      **{f"{lab}_amount": round(present[lab]["amount"], 2) if lab in present else None for lab in sides},
                      **{f"{lab}_rows": present[lab]["rows"] if lab in present else 0 for lab in sides},
                      "difference": round(max(amounts) - min(amounts), 2) if len(amounts) > 1 else round(amounts[0], 2),
                      "break_type": ("missing_" + "_".join(missing)) if missing else "amount_break"})
    await _save(state, items)
    return {"items": items}


register(StepType(
    "match_n", "Match several systems", "Matches two or more systems by key (e.g. purchase order, goods receipt, invoice), with many-to-one sums; keeps what does not agree.",
    MatchNCfg, _match_n, needs=lambda c: set(), tools=lambda c: {s.tool for s in c.sources}))


class IntakeCfg(Cfg):
    tool: str                          # e.g. documents.read_workbook
    args: dict[str, Any] = Field(default_factory=dict)
    columns: dict[str, str]            # item field: column in the file
    required: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    id_field: str


async def _intake(state, cfg: IntakeCfg, step_id):
    from agent_one_finance import gateway
    try:
        rows = (await _call(state, step_id, cfg.tool, _args(cfg.args, state["case_key"]))).get("rows", [])
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return _failed("INTAKE_FAILED", e)
    good, bad = [], []
    for n, r in enumerate(rows, start=1):
        it = {f: r.get(col) for f, col in cfg.columns.items()}
        it["source_row"] = n
        problems = [f"{f} is missing" for f in cfg.required if it.get(f) in (None, "")]
        for f in cfg.numbers:
            if it.get(f) not in (None, ""):
                try:
                    it[f] = float(str(it[f]).replace(",", ""))
                except ValueError:
                    problems.append(f"{f} is not a number ({it[f]!r})")
        it["item_id"] = str(it.get(cfg.id_field) or f"row-{n}")
        (bad if problems else good).append({**it, "intake_problems": problems} if problems else it)
    await _save(state, good)
    await _exclude(state, step_id, bad, "the row failed the file checks")
    return {"items": good}


register(StepType(
    "intake", "File intake", "Reads a file (a workbook from the documents service) into items with a column map and checks; rows that fail are kept aside, with why.",
    IntakeCfg, _intake, needs=lambda c: set(), tools=lambda c: {c.tool}))


class ExtractField(Cfg):
    name: str
    hint: str = ""
    required: bool = False
    pattern: str | None = None         # a regular expression with one group, used before (or instead of) the model


class ExtractCfg(Cfg):
    tool: str                          # e.g. documents.read_pdf
    args: dict[str, Any] = Field(default_factory=dict)
    fields: list[ExtractField] = Field(min_length=1)
    accept_confidence: float = Field(default=0.9, ge=0, le=1)
    # Regulated documents: every extracted value is checked by a person, whatever the confidence.
    regulated: bool = False
    id: str = "document"


async def _extract(state, cfg: ExtractCfg, step_id):
    from agent_one_finance import gateway
    from agent_one_finance.llm import ExtractRequest, llm
    try:
        res = await _call(state, step_id, cfg.tool, _args(cfg.args, state["case_key"]))
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return _failed("EXTRACT_FAILED", e)
    text = "\n".join(str(r.get("text", "")) for r in res.get("rows", []))
    values: dict[str, dict] = {}
    for f in cfg.fields:
        if f.pattern and (mt := re.search(f.pattern, text)):
            values[f.name] = {"value": mt.group(1).strip(), "quote": mt.group(0), "confidence": 1.0, "by": "pattern"}
    rest = [f for f in cfg.fields if f.name not in values]
    if rest:
        adapter = llm()
        if hasattr(adapter, "extract"):
            got = await adapter.extract(ExtractRequest(case_id=state["case_id"], text=text[:60_000],
                                                       fields=[f.model_dump() for f in rest]))
            for name, v in (got or {}).items():
                values[name] = {**v, "by": adapter.name}
    item = {"item_id": str(_value(cfg.args.get("name", cfg.id), {}, state["case_key"]) or cfg.id)}
    review = []
    for f in cfg.fields:
        v = values.get(f.name)
        grounded = bool(v and v.get("quote") and v["quote"] in text and str(v.get("value", "")) in v["quote"])
        conf = float((v or {}).get("confidence") or 0)
        item[f.name] = v.get("value") if v and grounded else None
        if not v or not grounded or conf < cfg.accept_confidence or cfg.regulated:
            if v or f.required:
                review.append({"field": f.name, "why": "not found" if not v else "not in the document" if not grounded
                               else "regulated: a person checks every value" if cfg.regulated else f"confidence {conf:.2f}",
                               "quote": (v or {}).get("quote")})
    item["extract_review"] = review
    item["extract_ok"] = not review
    await _save(state, [item])
    return {"items": [*state.get("items", []), item]}


register(StepType(
    "extract", "Read a document", "Reads fields from a document (patterns first, then the model); every value must appear in the document, and low-confidence or regulated values go to a person.",
    ExtractCfg, _extract, needs=lambda c: set(), tools=lambda c: {c.tool}))


# =====================================================================
# Phase 6 — time, context and parties
# =====================================================================

class Clock(Cfg):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,30}$")
    label: str
    starts: str = "case_opened"        # an item field (ISO time) or case_opened
    hours: float | None = Field(default=None, gt=0)
    business_days: int | None = Field(default=None, ge=1)
    warn_before_hours: float = 4
    pause_hours_field: str | None = None   # hours spent waiting on the client, added to the due time


class ClockCfg(Cfg):
    clocks: list[Clock] = Field(min_length=1)


def _add_business_days(at: datetime, n: int) -> datetime:
    d = at
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


async def _clock(state, cfg: ClockCfg, step_id):
    from agent_one_finance.db import get_session
    from agent_one_finance.models import Case
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        opened = case.opened_at.replace(tzinfo=None)
    items, earliest = [], {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for it in state["items"]:
        new = dict(it)
        for c in cfg.clocks:
            try:
                start = opened if c.starts == "case_opened" else rules._dt(it.get(c.starts))
            except Exception:
                new[f"clock_{c.id}_state"] = "unknown"
                continue
            due = start + timedelta(hours=c.hours) if c.hours else _add_business_days(start, c.business_days or 1)
            if c.pause_hours_field and isinstance(it.get(c.pause_hours_field), (int, float)):
                due += timedelta(hours=float(it[c.pause_hours_field]))
            state_ = "breached" if now > due else "due soon" if now > due - timedelta(hours=c.warn_before_hours) else "on time"
            new[f"clock_{c.id}_due"] = due.isoformat(timespec="minutes") + "Z"
            new[f"clock_{c.id}_state"] = state_
            if c.id not in earliest or due < earliest[c.id][0]:
                earliest[c.id] = (due, c)
        items.append(new)
    async with get_session() as s:
        case = await s.get(Case, state["case_id"])
        prev = dict(case.clock_state or {})
        case.clock_state = {cid: {"label": c.label, "due_at": due.isoformat() + "Z", "warn_before_hours": c.warn_before_hours,
                                  "warned": (prev.get(cid) or {}).get("warned", False),
                                  "breached": (prev.get(cid) or {}).get("breached", False)}
                            for cid, (due, c) in earliest.items()}
        await s.commit()
    await _save(state, items)
    return {"items": items}


register(StepType(
    "clock", "Clocks", "Starts service-level or regulatory clocks per item (hours or business days, paused for time waiting on the client); people are warned before and told on breach.",
    ClockCfg, _clock))


class TimelineSource(Cfg):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    time_field: str
    label: str


class TimelineCfg(Cfg):
    sources: list[TimelineSource] = Field(min_length=1)
    into: str = "timeline"
    for_model: bool = True             # the model sees it (protected) when it investigates


async def _timeline(state, cfg: TimelineCfg, step_id):
    from agent_one_finance import gateway
    rows = []
    for src in cfg.sources:
        try:
            got = (await _call(state, step_id, src.tool, _args(src.args, state["case_key"]))).get("rows", [])
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            got = [{src.time_field: None, "error": str(e)}]
        rows += [{"at": r.get(src.time_field), "source": src.label, **r} for r in got]
    rows.sort(key=lambda r: str(r.get("at") or ""))
    await _keep_dataset(state, step_id, cfg.into, step_id, rows)
    ctx = list(state.get("model_context") or [])
    if cfg.for_model:
        ctx.append({"name": cfg.into, "rows": rows[:200]})
    return {"datasets": {**(state.get("datasets") or {}), cfg.into: rows}, "model_context": ctx}


register(StepType(
    "timeline", "Timeline", "Builds one ordered timeline of events from several systems for the reviewer (and the model).",
    TimelineCfg, _timeline, needs=lambda c: set(), produces=lambda c: {ds(c.into)},
    tools=lambda c: {s.tool for s in c.sources}))


class LinkCfg(Cfg):
    match_on: list[str] = Field(min_length=1)            # item fields: client, account, counterparty…
    lookback_days: int = Field(default=365, ge=1, le=3650)
    capabilities: list[str] = Field(default_factory=list)   # empty = every capability
    limit: int = Field(default=5, ge=1, le=50)


async def _link(state, cfg: LinkCfg, step_id):
    from sqlalchemy import select

    from agent_one_finance.db import get_session
    from agent_one_finance.models import Case, CaseItem
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=cfg.lookback_days)
    items = []
    async with get_session() as s:
        for it in state["items"]:
            related: dict[str, dict] = {}
            for f in cfg.match_on:
                v = it.get(f)
                if v in (None, ""):
                    continue
                q = (select(Case.case_id, Case.subject, Case.status, Case.outcome, Case.capability_id)
                     .join(CaseItem, CaseItem.case_id == Case.case_id)
                     .where(CaseItem.payload[f].astext == str(v), Case.case_id != state["case_id"],
                            Case.opened_at >= since, Case.shadow_of.is_(None)))
                if cfg.capabilities:
                    q = q.where(Case.capability_id.in_(cfg.capabilities))
                for cid, subj, st, out, cap in (await s.execute(q.limit(cfg.limit))).all():
                    related.setdefault(cid, {"case_id": cid, "subject": subj, "status": st, "outcome": out,
                                             "capability_id": cap, "on": f})
            items.append({**it, "related": list(related.values())[: cfg.limit], "related_count": len(related)})
    await _save(state, items)
    return {"items": items}


register(StepType(
    "link", "Related cases", "Finds earlier cases about the same client, account or counterparty (any capability) and shows how they ended.",
    LinkCfg, _link))


class ScreenCfg(Cfg):
    list: str                          # a data set of names (internal lists, extracts supplied by the control function)
    fields: list[str] = Field(min_length=1)
    list_field: str = "name"
    threshold: float = Field(default=0.85, gt=0, le=1)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\b(ltd|limited|plc|inc|llc|gmbh|sa|ag|pte|bv)\b", "", str(s).lower())).strip()


async def _screen(state, cfg: ScreenCfg, step_id):
    names = [(r.get(cfg.list_field), r) for r in (state.get("datasets") or {}).get(cfg.list, []) if r.get(cfg.list_field)]
    items = []
    for it in state["items"]:
        cands = []
        for f in cfg.fields:
            v = it.get(f)
            if not v:
                continue
            for name, row in names:
                score = difflib.SequenceMatcher(None, _norm(v), _norm(name)).ratio()
                if score >= cfg.threshold:
                    cands.append({"field": f, "value": v, "candidate": name, "score": round(score, 2),
                                  "list_id": row.get("id")})
        items.append({**it, "screen_candidates": sorted(cands, key=lambda c: -c["score"])[:5],
                      "screen_candidate": bool(cands)})          # a candidate only; a person decides
    await _save(state, items)
    return {"items": items}


register(StepType(
    "screen", "Name screening (candidates)", "Fuzzy-matches names against a list and marks candidate matches for a person; it never clears or confirms a match.",
    ScreenCfg, _screen, needs=lambda c: {"items", ds(c.list)}, dataset_refs=lambda c: {c.list}))


class OutreachCfg(Cfg):
    tool: str                          # the bank's channel: a write tool (email, SWIFT MT199, portal)
    roles: list[str] = Field(min_length=1)   # who approves sending, at the tollgate before this step
    when: str = "status == 'proposed'"


async def _outreach(state, cfg: OutreachCfg, step_id):
    """Sends each group's drafted message (`compose`), once a person approved
    sending at the tollgate before this step."""
    from agent_one_finance import gateway
    s = _steps()
    by = next((n.get("by") for n in reversed(state.get("gate_notes") or []) if n.get("step") == step_id), None) \
        or next((g for g in reversed(state.get("gates_passed") or []) if g), None)
    findings = dict(state.get("findings") or {})
    rows = []
    for g in state.get("groups") or []:
        f = dict(findings.get(g["group_id"]) or {})
        msg = f.get("draft_message")
        try:
            go = msg and rules.evaluate(cfg.when, _group_env(state, g, f))
        except rules.ExpressionError:
            go = False
        if not go:
            continue
        try:
            res = await _call(state, step_id, cfg.tool, {**msg, "case_ref": state["case_id"],
                                                         "idempotency_key": f"{state['case_id']}:{g['group_id']}:{step_id}"},
                              write_by=by or "tollgate")
            f["sent_message"] = {**msg, "message_id": res.get("message_id"), "approved_by": by}
            rows.append({"group_id": g["group_id"], "to": msg["to"], "message_id": res.get("message_id"), "approved_by": by})
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            f["sent_message"] = {**msg, "error": str(e)}
            rows.append({"group_id": g["group_id"], "to": msg["to"], "error": str(e)})
        findings[g["group_id"]] = f
        await s._save_group_finding(state["case_id"], g["group_id"], f)
    await _keep_dataset(state, step_id, "outreach", cfg.tool, rows)
    return {"findings": findings, "datasets": {**(state.get("datasets") or {}), "outreach": rows}}


register(StepType(
    "outreach", "Send to the other party", "Sends each drafted message (client, counterparty, another team) through the bank's channel, after a person approves sending at the tollgate before it.",
    OutreachCfg, _outreach, needs=lambda c: {"groups", "findings"}, produces=lambda c: {"findings"},
    tools=lambda c: {c.tool}, expressions=lambda c: [("when", c.when)],
    extra={"writes": lambda c: {c.tool}, "person": True}))
