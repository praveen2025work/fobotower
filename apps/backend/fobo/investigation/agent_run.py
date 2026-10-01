"""One agent-harness session per L4 rec run.

The Reason step settles what rules can, then hands everything left to this
module: the unsettled breaks are grouped into patterns, ONE session is
started for the whole rec, it is waited on (start, then poll), and the
response is mapped back to a verdict per break.

The `agent_session` row makes this restart safe (spec §3):

    none       create (starting), commit, start, mark running, commit, wait
    starting   the process died before the harness answered: failed, escalate
    running    resume waiting on the stored harness_session_id
    completed  reuse the stored response; no new session
    failed     escalate with the stored error

Committing before the wait means no transaction stays open while polling and
the MCP server (its own DB session) can see the row and honour its token.

`session=None` (unit tests without a database) skips persistence, the
restart table and the source_call record, but still starts, polls and maps,
so the mapping and the guards stay testable without a database.
"""

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select

from fobo.db.models_ops import SourceCall
from fobo.grounding.recorder import GroundingRecorder
from fobo.investigation.settings import settings
from fobo.reasoning import agent_sessions
from fobo.reasoning.contracts import RecVerdict, SkillVerdict
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable
from fobo.reasoning.requests import build_request

UNGROUPED = "UNGROUPED"
UNGROUPED_LABEL = "No cause identified"
NOT_COVERED = "not covered by the agent's response"
REDACTED = "<redacted>"
SESSION_TOOL = "agent.session"
NEVER_STARTED = (
    "agent session never started: the process stopped before the harness answered"
)


@dataclass(frozen=True)
class AgentOutcome:
    rec_verdict: RecVerdict | None
    harness_session_id: str | None
    error: str | None
    payload: dict = field(default_factory=dict)


def _attr(group, name):
    """Pattern groups are PatternGroup models, or dicts from an old checkpoint."""
    return group[name] if isinstance(group, dict) else getattr(group, name)


def pattern_of(pattern_groups) -> dict[str, tuple[str, str]]:
    """break_id -> (pattern_code, label) for every grouped break."""
    return {
        bid: (_attr(g, "pattern_code"), _attr(g, "label"))
        for g in pattern_groups or []
        for bid in _attr(g, "break_ids")
    }


def _amount(evidence: dict) -> float:
    return abs(evidence.get("break_amount") or 0)


def build_patterns(
    unsettled: dict[str, dict], pattern_groups, sample_size: int
) -> list[dict]:
    """The request's patterns: count, total and the largest breaks as a sample.
    The agent fetches the rest through MCP."""
    lookup = pattern_of(pattern_groups)
    members: dict[str, list[dict]] = defaultdict(list)
    labels: dict[str, str] = {}
    for bid, evidence in unsettled.items():
        code, label = lookup.get(bid, (UNGROUPED, UNGROUPED_LABEL))
        members[code].append(evidence)
        labels[code] = label
    patterns = [
        {
            "pattern_code": code,
            "label": labels[code],
            "break_count": len(items),
            "total_amount": round(sum(_amount(e) for e in items), 2),
            "sample": sorted(items, key=_amount, reverse=True)[:sample_size],
        }
        for code, items in members.items()
    ]
    return sorted(patterns, key=lambda p: (-p["break_count"], p["pattern_code"]))


def map_verdicts(
    rec_verdict: RecVerdict, unsettled: dict[str, dict]
) -> dict[str, tuple[SkillVerdict | None, str | None]]:
    """Per unsettled break: its exception, else its pattern's verdict, else
    nothing. Exceptions naming breaks outside the request are ignored."""
    by_pattern: dict[str, SkillVerdict] = {}
    for p in rec_verdict.patterns:
        by_pattern.setdefault(p.pattern_code, p)
    by_break: dict[str, SkillVerdict] = {}
    for e in rec_verdict.exceptions:
        by_break.setdefault(e.break_id, e.verdict)
    mapped = {}
    for bid, evidence in unsettled.items():
        verdict = by_break.get(bid) or by_pattern.get(evidence.get("pattern_code"))
        mapped[bid] = (verdict, None) if verdict is not None else (None, NOT_COVERED)
    return mapped


def _jsonable(value):
    """Evidence goes into JSONB and over HTTP; dates and the like become str."""
    return json.loads(json.dumps(value, default=str))


def _caller(state) -> dict:
    caller = state.get("caller")
    if caller is None:
        return {}
    return caller.model_dump() if hasattr(caller, "model_dump") else dict(caller)


def _request(state, unsettled: dict, token: str) -> dict:
    cfg = settings().reason
    total = len(state.get("breaks", []))
    return build_request(
        correlation_id=state.get("investigation_session_id", ""),
        rec={
            "reconciliation_id": state.get("reconciliation_id"),
            "master_book": state.get("master_book"),
            "business_date": str(state.get("business_date")),
            "run_id": state.get("run_id"),
        },
        patterns=build_patterns(
            unsettled, state.get("pattern_groups"), cfg.sample_breaks_per_pattern
        ),
        already_established={
            "total": total,
            "settled_by_rules": total - len(unsettled),
            "unsettled": len(unsettled),
        },
        mcp_token=token,
    )


def _redacted(request: dict) -> dict:
    if "mcp" not in request:
        return request
    return {**request, "mcp": {**request["mcp"], "token": REDACTED}}


def _response(status: HarnessStatus) -> dict:
    """What is kept for audit and reuse: the raw payload, with the parsed
    output added when the adapter's payload has none (the direct reasoner)."""
    output = status.output.model_dump(mode="json") if status.output else None
    return {"output": output, **status.payload}


async def _wait(reasoner, status: HarnessStatus, *, sleep, clock) -> HarnessStatus:
    """Poll until the session leaves `running`, or fail it past max_wait."""
    cfg = settings().session_service
    deadline = clock() + cfg.max_wait_seconds
    while status.status == "running":
        if clock() >= deadline:
            return HarnessStatus(
                session_id=status.session_id,
                status="failed",
                payload=status.payload,
                error=f"agent session timed out after {cfg.max_wait_seconds:g}s",
            )
        await sleep(cfg.poll_interval_seconds)
        status = await reasoner.poll(status.session_id)
    return status


def _outcome(status: HarnessStatus) -> AgentOutcome:
    if status.status == "completed":
        return AgentOutcome(status.output, status.session_id, None, status.payload)
    return AgentOutcome(None, status.session_id, status.error, status.payload)


async def _start_and_wait(reasoner, request, *, sleep, clock) -> HarnessStatus:
    status = await reasoner.start(request)
    return await _wait(reasoner, status, sleep=sleep, clock=clock)


async def _run_without_db(state, unsettled, reasoner, *, sleep, clock) -> AgentOutcome:
    token, _ = agent_sessions.new_token()
    try:
        status = await _start_and_wait(
            reasoner, _jsonable(_request(state, unsettled, token)), sleep=sleep, clock=clock
        )
    except ReasoningUnavailable as exc:
        return AgentOutcome(None, None, str(exc))
    return _outcome(status)


def _from_row(row) -> AgentOutcome:
    if row.status == "completed":
        try:
            verdict = RecVerdict.model_validate((row.response or {}).get("output"))
        except ValidationError as exc:
            return AgentOutcome(
                None, row.harness_session_id,
                f"stored agent response is unparseable: {exc}", row.response or {},
            )
        return AgentOutcome(verdict, row.harness_session_id, None, row.response or {})
    return AgentOutcome(None, row.harness_session_id, row.error, row.response or {})


async def _finish(session, row, status: HarnessStatus) -> AgentOutcome:
    if status.status == "completed":
        await agent_sessions.mark_completed(session, row, _response(status))
    else:
        await agent_sessions.mark_failed(session, row, status.error, status.payload or None)
    await session.commit()
    return _outcome(status)


async def _fail(session, row, error: str, harness_session_id=None) -> AgentOutcome:
    await agent_sessions.mark_failed(session, row, error)
    await session.commit()
    return AgentOutcome(None, harness_session_id or row.harness_session_id, error)


async def _new_session(session, state, unsettled, reasoner, *, sleep, clock):
    token, token_hash = agent_sessions.new_token()
    request = _jsonable(_request(state, unsettled, token))
    row = await agent_sessions.create(
        session,
        investigation_session_id=state["investigation_session_id"],
        token_hash=token_hash,
        caller=_caller(state),
        business_date=state["business_date"],
        breaks=_jsonable(unsettled),
        request=_redacted(request),
    )
    await session.commit()
    try:
        status = await reasoner.start(request)
        await agent_sessions.mark_running(session, row, status.session_id)
        await session.commit()
        status = await _wait(reasoner, status, sleep=sleep, clock=clock)
    except ReasoningUnavailable as exc:
        return await _fail(session, row, str(exc))
    return await _finish(session, row, status)


async def _resume(session, row, reasoner, *, sleep, clock) -> AgentOutcome:
    try:
        status = await reasoner.poll(row.harness_session_id)
        status = await _wait(reasoner, status, sleep=sleep, clock=clock)
    except ReasoningUnavailable as exc:
        return await _fail(session, row, str(exc))
    return await _finish(session, row, status)


async def _record(session, sid: str, unsettled: dict, outcome: AgentOutcome, latency_ms):
    """One agent.session source_call per investigation, whatever the outcome."""
    existing = await session.scalar(
        select(SourceCall.call_id).where(
            SourceCall.investigation_session_id == sid,
            SourceCall.tool_name == SESSION_TOOL,
        ).limit(1)
    )
    if existing is not None:
        return
    patterns = sorted({e.get("pattern_code", UNGROUPED) for e in unsettled.values()})
    tool_calls = (outcome.payload or {}).get("tool_calls") or []
    await GroundingRecorder(session, sid).record(
        application="agent",
        tool=SESSION_TOOL,
        params={
            "harness_session_id": outcome.harness_session_id,
            "patterns": patterns,
            "breaks": sorted(unsettled),
        },
        row_count=len(unsettled),
        summary=outcome.rec_verdict.summary if outcome.rec_verdict else outcome.error,
        error=outcome.error,
        rows=[{"tool": c.get("tool"), "arguments": c.get("arguments")} for c in tool_calls],
        latency_ms=latency_ms,
    )
    await session.commit()


async def run_agent(
    session,
    state,
    unsettled: dict[str, dict],
    *,
    reasoner,
    sleep=asyncio.sleep,
    clock=time.monotonic,
) -> AgentOutcome:
    """Run (or pick up) the one agent session for this rec run.

    `unsettled` is break_id -> evidence (carrying `pattern_code`). Never
    raises ReasoningUnavailable: an unavailable harness is an outcome with
    an error, and the step escalates on it.
    """
    if session is None:
        return await _run_without_db(state, unsettled, reasoner, sleep=sleep, clock=clock)

    sid = state["investigation_session_id"]
    began = clock()
    row = await agent_sessions.get_for_investigation(session, sid)
    if row is None:
        outcome = await _new_session(
            session, state, unsettled, reasoner, sleep=sleep, clock=clock
        )
    elif row.status == "starting":
        outcome = await _fail(session, row, NEVER_STARTED)
    elif row.status == "running":
        outcome = await _resume(session, row, reasoner, sleep=sleep, clock=clock)
    else:
        outcome = _from_row(row)
    await _record(session, sid, unsettled, outcome, int((clock() - began) * 1000))
    return outcome
