"""Eval sets and shadow runs: try a version on what people already decided.

Test set: past cases of a capability (or one team's group) whose groups
people settled — what they approved or rejected, in their words, and the
verdict when there was a playbook.

Shadow run: each of those cases is opened again, hidden (`shadow_of`), on
the version under test — a draft not yet approved, or the live one after a
model change — and run to its review pause, through the same gateway (real
reads, audited; nothing is ever written: a shadow never reaches publish).

Score, per group matched by its key:
  outcome     approved before and proposed now → agree; rejected before and
              proposed now → disagree; escalated now → escalated (safe, but
              less automation)
  verdict     the same playbook verdict
  wording     a judge's 0–1 similarity of the new explanation to the
              approved one (the model when there is one; word overlap otherwise)
plus groups that went missing or are new. Each run is a span in Phoenix
(`eval.run`, one `eval.case` per case) with the scores as attributes.

    POST /api/capabilities/{id}/evals   {version?, team_group?, group_version?, limit?}
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from agent_one_finance import capabilities, runner
from agent_one_finance import groups as team_groups
from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import Case, CapabilityVersion, Decision, EvalRun, GroupVersion, ProposalGroup
from agent_one_finance.observability import span

log = logging.getLogger("agent_one_finance.evals")
_tasks: set[asyncio.Task] = set()


class EvalError(ValueError):
    pass


def _key(group_key: dict) -> str:
    return json.dumps(group_key, sort_keys=True)


async def _target(capability_id: str, version: int | None, team_group: str | None,
                  group_version: int | None) -> tuple[int, int | None, Manifest]:
    """The manifest under test: a capability version (live by default),
    merged with a group version (live by default) when testing a group."""
    async with get_session() as s:
        if version is None:
            version, _ = await capabilities.active(capability_id)
        row = await s.get(CapabilityVersion, (capability_id, version))
        if row is None:
            raise EvalError(f"{capability_id} has no version {version}")
        base = Manifest.model_validate(row.manifest)
        if not team_group:
            return version, None, base
        if group_version is None:
            group_version = (await team_groups.active_group(capability_id, team_group))[0]
        grow = await s.get(GroupVersion, (capability_id, team_group, group_version))
        if grow is None:
            raise EvalError(f"group {team_group} has no version {group_version}")
    m, found = team_groups.effective(base, team_groups.GroupConfig.model_validate(grow.config))
    if found:
        raise EvalError("that group version does not fit that capability version: " + "; ".join(found))
    return version, group_version, m


async def test_set(capability_id: str, team_group: str | None, limit: int) -> list[dict]:
    """Past cases whose every group people settled, newest first."""
    from agent_one_finance.cases import _case_items, _settle

    async with get_session() as s:
        q = select(Case).where(Case.capability_id == capability_id, Case.shadow_of.is_(None),
                               Case.status.in_(("completed", "awaiting_publish", "failed")))
        if team_group:
            q = q.where(Case.team_group == team_group)
        cases = (await s.execute(q.order_by(Case.opened_at.desc()).limit(limit * 3))).scalars().all()
        out = []
        for c in cases:
            m = await runner.pinned(c)
            groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.case_id == c.case_id))).scalars().all()
            decisions = (await s.execute(select(Decision).where(Decision.case_id == c.case_id))).scalars().all()
            items = await _case_items(s, c.case_id)
            expected = {}
            for g in groups:
                settled = _settle(m, g, decisions, items)
                if settled is None:
                    break
                f = g.finding or {}
                expected[_key(g.group_key)] = {
                    "label": g.label, "action": settled["action"],
                    "words": settled.get("comment") or f.get("comment") or "",
                    "verdict": f.get("verdict"), "decided_by": settled["decided_by"]}
            else:
                if expected:
                    out.append({"case_id": c.case_id, "case_key": c.case_key, "team_group": c.team_group,
                                "expected": expected})
            if len(out) >= limit:
                break
    return out


def _overlap(a: str, b: str) -> float:
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return round(len(wa & wb) / len(wa | wb), 3) if wa | wb else 1.0


async def _judge(expected: str, actual: str) -> float:
    from agent_one_finance.llm import llm

    judge = getattr(llm(), "judge", None)
    if judge is None or not expected or not actual:
        return _overlap(expected, actual)
    try:
        return float(await judge(expected, actual))
    except Exception:
        log.exception("judge failed; using word overlap")
        return _overlap(expected, actual)


def _outcome(expected_action: str, status: str) -> str:
    if status == "escalated":
        return "agree" if expected_action == "reject" else "escalated"
    return "agree" if expected_action == "approve" else "disagree"


async def _shadow(run_id: str, src: dict, version: int, group_version: int | None, m: Manifest,
                  starter: Caller) -> dict:
    """Replay one past case on the version under test; compare at the review pause."""
    shadow_id = f"{src['case_id']}.shadow.{run_id[:8]}"
    async with get_session() as s:
        s.add(Case(case_id=shadow_id, root_case_id=shadow_id, shadow_of=src["case_id"], eval_run_id=run_id,
                   capability_id=m.id, manifest_version=version, team_group=src["team_group"],
                   team_group_version=group_version, manifest=m.model_dump(by_alias=True),
                   case_key=src["case_key"], subject=f"shadow of {src['case_id']}",
                   scope={sc: src["case_key"].get(f) for f, sc in m.case.scopes.items()},
                   status="running", opened_by=starter.user_id, run_as=starter.as_dict()))
        await s.commit()
    await runner.run_case(shadow_id, "open")
    async with get_session() as s:
        case = await s.get(Case, shadow_id)
        groups = (await s.execute(select(ProposalGroup).where(ProposalGroup.case_id == shadow_id))).scalars().all()
        reached = case.status
        case.status = "shadow"                 # never on anyone's desk, never published
        await s.commit()
    now = {_key(g.group_key): g for g in groups}
    rows, cost = [], 0.0
    for key, e in src["expected"].items():
        g = now.get(key)
        if g is None:
            rows.append({"group": e["label"], "outcome": "missing", "expected": e})
            continue
        f = g.finding or {}
        cost += float((f.get("usage") or {}).get("cost_usd") or 0)
        rows.append({"group": g.label, "outcome": _outcome(e["action"], f.get("status", "")),
                     "verdict_match": (f.get("verdict") == e["verdict"]) if e.get("verdict") else None,
                     "wording": await _judge(e["words"], f.get("comment", "")),
                     "expected": e, "now": {k: f.get(k) for k in ("status", "comment", "reason", "verdict", "decided_by")}})
    rows += [{"group": g.label, "outcome": "new", "now": {"status": (g.finding or {}).get("status")}}
             for k, g in now.items() if k not in src["expected"]]
    return {"case_id": src["case_id"], "shadow_case_id": shadow_id, "reached": reached, "groups": rows,
            "cost_usd": round(cost, 4)}


def summarise(results: list[dict]) -> dict:
    rows = [g for r in results for g in r["groups"]]
    compared = [g for g in rows if g["outcome"] in ("agree", "disagree", "escalated")]
    n = len(compared)
    verdicts = [g["verdict_match"] for g in compared if g.get("verdict_match") is not None]
    words = [g["wording"] for g in compared if g.get("wording") is not None]

    def count(o):
        return sum(1 for g in rows if g["outcome"] == o)
    return {"cases": len(results), "groups_compared": n,
            "agree": count("agree"), "disagree": count("disagree"), "escalated": count("escalated"),
            "missing": count("missing"), "new": count("new"),
            "agreement_rate": round(count("agree") / n, 3) if n else None,
            "verdict_match_rate": round(sum(verdicts) / len(verdicts), 3) if verdicts else None,
            "wording_mean": round(sum(words) / len(words), 3) if words else None,
            "cost_usd": round(sum(r["cost_usd"] for r in results), 4)}


async def _run(run_id: str, version: int, group_version: int | None, m: Manifest, team_group: str | None,
               limit: int, starter: Caller) -> None:
    results = []
    try:
        with span("eval.run", root=True, capability_id=m.id, version=version, team_group=team_group or "",
                  run_id=run_id) as sp:
            for src in await test_set(m.id, team_group, limit):
                with span("eval.case", case_id=src["case_id"]) as cs:
                    r = await _shadow(run_id, src, version, group_version, m, starter)
                    part = summarise([r])
                    for k in ("agreement_rate", "verdict_match_rate", "wording_mean"):
                        if part[k] is not None:
                            cs.set_attribute(f"eval.{k}", part[k])
                results.append(r)
            summary = summarise(results)
            for k, v in summary.items():
                if v is not None:
                    sp.set_attribute(f"eval.{k}", v)
        status, error = "done", None
    except Exception as e:
        log.exception("eval run %s failed", run_id)
        summary, status, error = summarise(results), "failed", f"{type(e).__name__}: {e}"
    async with get_session() as s:
        row = await s.get(EvalRun, run_id)
        row.status, row.summary, row.results, row.error = status, summary, results, error
        row.finished_at = datetime.now(timezone.utc)
        await s.commit()


async def start(capability_id: str, caller: Caller, *, version: int | None = None,
                team_group: str | None = None, group_version: int | None = None, limit: int = 20) -> str:
    """Owners of the capability (or of the group under test) start an eval run."""
    _, live = await capabilities.active(capability_id)
    allowed = capabilities.is_owner(caller, live)
    if team_group and not allowed:
        _, cfg, _ = await team_groups.active_group(capability_id, team_group)
        allowed = team_groups.is_group_owner(caller, cfg)
    if not allowed:
        raise PermissionError(f"{caller.user_id} does not own {capability_id}" + (f"/{team_group}" if team_group else ""))
    if not team_group and await team_groups.active_groups(capability_id):
        raise EvalError(f"{capability_id} runs per group: choose a team_group to evaluate")
    version, group_version, m = await _target(capability_id, version, team_group, group_version)
    run_id = uuid.uuid4().hex
    async with get_session() as s:
        s.add(EvalRun(run_id=run_id, capability_id=capability_id, version=version, team_group=team_group,
                      group_version=group_version, status="running", started_by=caller.user_id))
        await s.commit()
    work = _run(run_id, version, group_version, m, team_group, max(1, min(limit, 200)), caller)
    if settings().run_mode == "inline":
        await work
    else:
        task = asyncio.create_task(work, name=f"aof:eval:{run_id}")
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return run_id


def _row(r: EvalRun, with_results: bool = False) -> dict:
    out = {"run_id": r.run_id, "capability_id": r.capability_id, "version": r.version,
           "team_group": r.team_group, "group_version": r.group_version, "status": r.status,
           "started_by": r.started_by, "started_at": r.started_at, "finished_at": r.finished_at,
           "summary": r.summary, "error": r.error}
    if with_results:
        out["results"] = r.results
    return out


async def runs(capability_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(EvalRun).where(EvalRun.capability_id == capability_id)
                                .order_by(EvalRun.started_at.desc()).limit(50))).scalars().all()
    return [_row(r) for r in rows]


async def get(run_id: str) -> dict:
    async with get_session() as s:
        r = await s.get(EvalRun, run_id)
    if r is None:
        raise LookupError(run_id)
    return _row(r, with_results=True)
