"""One agent session per L4 run: grouping, verdict mapping and the lifecycle.

The pure parts (patterns, mapping, start/poll with session=None) need no
database. The lifecycle and restart tests run against the test database,
because restart safety is a property of the committed agent_session row.
No test really sleeps: the waiting loop takes a fake clock and sleep.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from fobo.contracts.models import Caller, PatternGroup
from fobo.db.base import get_session
from fobo.db.models_ops import SourceCall
from fobo.db.models_session import InvestigationSession
from fobo.investigation.agent_run import build_patterns, map_verdicts, run_agent
from fobo.reasoning import agent_sessions as repo
from fobo.reasoning.contracts import (
    BreakException, CheckPerformed, Classification, PatternVerdict, RecVerdict,
    Remediation, RootCause, SkillVerdict,
)
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable

SID = "sess-r-2031"


def _skill(verdict="POST", side="BO", statement="cause"):
    return dict(
        break_summary="s",
        checks_performed=[CheckPerformed(test_id="FO-3", checked="c", result="Fail", evidence="e")],
        root_cause=RootCause(established=True, statement=statement, side=side),
        classification=Classification(category_code="G", category_name="Corporate action break",
                                      deterministic=False),
        verdict=verdict,
        verdict_reason="r",
        remediation=Remediation(who_to_engage=["desk"], what_to_raise=["DQ"]),
        end_state_validation="open",
        requires_sme_review=True,
    )


def _rec(patterns=("P-204",), exceptions=(), summary="all explained"):
    return RecVerdict(
        summary=summary,
        patterns=[PatternVerdict(pattern_code=p, **_skill(statement=f"cause {p}")) for p in patterns],
        exceptions=[
            BreakException(break_id=b, reason="differs", verdict=SkillVerdict(**_skill(verdict="ESCALATE",
                                                                                    statement=f"own {b}")))
            for b in exceptions
        ],
    )


def _ev(bid, amount, code="P-204"):
    return {"break_id": bid, "break_amount": amount, "pattern_code": code}


GROUPS = [
    PatternGroup(group_id=f"{SID}:P-204", pattern_code="P-204", label="FX timing lag",
                 mode="auto", break_ids=["B-1", "B-2"]),
    PatternGroup(group_id=f"{SID}:LATE-BOOK", pattern_code="LATE-BOOK", label="Late trade booking",
                 mode="manual", break_ids=["B-3"]),
]


def _state(sid=SID):
    return {
        "investigation_session_id": sid,
        "reconciliation_id": "R-2031",
        "master_book": "FICR-MB",
        "business_date": date(2026, 8, 3),
        "run_id": "run-R-2031-20260803",
        "caller": Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-1"], region="APAC"),
        "breaks": [{"break_id": b} for b in ("B-1", "B-2", "B-3", "B-4")],
        "pattern_groups": GROUPS,
    }


UNSETTLED = {"B-1": _ev("B-1", -10.0), "B-2": _ev("B-2", 30.0), "B-3": _ev("B-3", 5.0, "LATE-BOOK")}


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now


class FakeHarness:
    """A scripted port: `start` returns the first status, each `poll` the next."""

    name = "fake"

    def __init__(self, start=None, polls=(), start_error=None, on_poll=None):
        self._start = start
        self._polls = list(polls)
        self._start_error = start_error
        self._on_poll = on_poll
        self.starts = []
        self.polled = []

    async def start(self, request):
        self.starts.append(request)
        if self._start_error:
            raise ReasoningUnavailable(self._start_error)
        return self._start

    async def poll(self, session_id):
        self.polled.append(session_id)
        if self._on_poll:
            await self._on_poll()
        item = self._polls.pop(0) if len(self._polls) > 1 else self._polls[0]
        if isinstance(item, Exception):
            raise item
        return item


def _running(sid="h-1"):
    return HarnessStatus(session_id=sid, status="running", payload={"status": "running"})


def _completed(rec=None, sid="h-1", tool_calls=None):
    rec = rec or _rec(("P-204", "LATE-BOOK"))
    payload = {"session_id": sid, "status": "completed", "output": rec.model_dump(mode="json"),
               "tool_calls": tool_calls or [], "total_cost_usd": 0.12, "num_turns": 9}
    return HarnessStatus(session_id=sid, status="completed", output=rec, payload=payload)


def _failed(sid="h-1"):
    return HarnessStatus(session_id=sid, status="failed", payload={"status": "failed"},
                         error="E42 — harness crashed")


# ---------- build_patterns ----------


def test_build_patterns_groups_counts_totals_and_samples():
    unsettled = {f"B-{i}": _ev(f"B-{i}", amt) for i, amt in enumerate([1.0, -9.5, 3.333, None, -2.0, 7.0])}
    unsettled["B-9"] = _ev("B-9", 4.0, "LATE-BOOK")
    unsettled["B-X"] = _ev("B-X", 2.0)
    groups = [
        PatternGroup(group_id="g1", pattern_code="P-204", label="FX timing lag", mode="auto",
                     break_ids=[f"B-{i}" for i in range(6)]),
        PatternGroup(group_id="g2", pattern_code="LATE-BOOK", label="Late trade booking", mode="manual",
                     break_ids=["B-9"]),
    ]
    patterns = build_patterns(unsettled, groups, 3)
    assert [p["pattern_code"] for p in patterns] == ["P-204", "LATE-BOOK", "UNGROUPED"]
    fx = patterns[0]
    assert fx["label"] == "FX timing lag"
    assert fx["break_count"] == 6
    assert fx["total_amount"] == round(1.0 + 9.5 + 3.333 + 0 + 2.0 + 7.0, 2)
    assert [s["break_id"] for s in fx["sample"]] == ["B-1", "B-5", "B-2"]
    ungrouped = patterns[2]
    assert ungrouped["label"] == "No cause identified"
    assert ungrouped["break_count"] == 1


def test_build_patterns_ties_order_by_code():
    unsettled = {"B-1": _ev("B-1", 1.0), "B-3": _ev("B-3", 1.0)}
    groups = [GROUPS[1], GROUPS[0]]
    assert [p["pattern_code"] for p in build_patterns(unsettled, groups, 5)] == ["LATE-BOOK", "P-204"]


# ---------- map_verdicts ----------


def test_pattern_verdict_applies_and_exception_overrides():
    mapped = map_verdicts(_rec(("P-204", "LATE-BOOK"), exceptions=("B-2", "B-99")), UNSETTLED)
    assert mapped["B-1"][0].root_cause.statement == "cause P-204"
    assert mapped["B-2"][0].root_cause.statement == "own B-2"
    assert mapped["B-3"][0].root_cause.statement == "cause LATE-BOOK"
    assert "B-99" not in mapped
    assert all(note is None for _, note in mapped.values())


def test_a_break_not_covered_has_no_verdict():
    mapped = map_verdicts(_rec(("P-204",)), UNSETTLED)
    assert mapped["B-3"] == (None, "not covered by the agent's response")
    assert mapped["B-1"][0] is not None


# ---------- run_agent without a database ----------


async def test_a_completed_start_is_not_polled():
    h = FakeHarness(start=_completed())
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert len(h.starts) == 1 and h.polled == []
    assert out.error is None and out.harness_session_id == "h-1"
    assert out.rec_verdict.summary == "all explained"
    req = h.starts[0]
    assert req["correlation_id"] == SID
    assert req["inputs"]["rec"] == {"reconciliation_id": "R-2031", "master_book": "FICR-MB",
                                    "business_date": "2026-08-03", "run_id": "run-R-2031-20260803"}
    assert req["inputs"]["already_established"] == {"total": 4, "settled_by_rules": 1, "unsettled": 3}
    assert {p["pattern_code"] for p in req["inputs"]["patterns"]} == {"P-204", "LATE-BOOK"}


async def test_running_then_completed_through_polls():
    h = FakeHarness(start=_running(), polls=[_running(), _completed()])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert h.polled == ["h-1", "h-1"]
    assert t.sleeps == [5.0, 5.0]
    assert out.error is None and out.rec_verdict is not None


async def test_a_session_that_never_completes_times_out():
    h = FakeHarness(start=_running(), polls=[_running()])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.rec_verdict is None
    assert "timed out" in out.error and "900" in out.error
    assert t.now >= 900
    assert len(h.polled) == 180


async def test_poll_errors_are_tolerated_up_to_three_in_a_row():
    boom = ReasoningUnavailable("blip")
    h = FakeHarness(start=_running(), polls=[boom, boom, _completed()])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.error is None and out.rec_verdict is not None


async def test_a_successful_poll_resets_the_poll_failure_count():
    boom = ReasoningUnavailable("blip")
    h = FakeHarness(start=_running(), polls=[boom, boom, boom, _running(), boom, boom, boom, _completed()])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.error is None


async def test_four_consecutive_poll_errors_fail_the_session():
    h = FakeHarness(start=_running(), polls=[ReasoningUnavailable("down")])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.rec_verdict is None and out.error == "down"
    assert len(h.polled) == 4


async def test_a_failed_harness_carries_its_error():
    h = FakeHarness(start=_running(), polls=[_failed()])
    t = FakeTime()
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.rec_verdict is None and out.error == "E42 — harness crashed"
    assert out.harness_session_id == "h-1"


async def test_an_unavailable_harness_is_an_error_not_an_exception():
    h = FakeHarness(start_error="connection refused")
    out = await run_agent(None, _state(), UNSETTLED, reasoner=h)
    assert out.rec_verdict is None and out.error == "connection refused"


# ---------- run_agent lifecycle against the database ----------


async def _investigation(sid=SID):
    async with get_session() as s:
        s.add(InvestigationSession(investigation_session_id=sid, reconciliation_id="R-2031",
                                   master_book="FICR-MB", business_date=date(2026, 8, 3),
                                   run_id="run-R-2031-20260803", status="analysing"))
        await s.commit()


async def _row(sid=SID):
    async with get_session() as s:
        return await repo.get_for_investigation(s, sid)


async def _agent_calls(sid=SID):
    async with get_session() as s:
        return (await s.scalars(select(SourceCall).where(
            SourceCall.investigation_session_id == sid, SourceCall.tool_name == "agent.session"))).all()


async def test_lifecycle_commits_before_waiting_and_stores_the_response(monkeypatch):
    monkeypatch.setenv("FOBO_MCP_URL", "http://localhost:8100/mcp")
    await _investigation()
    seen = []

    async def peek():
        row = await _row()
        seen.append((row.status, row.harness_session_id))

    calls = [{"tool": "mcp__fobo__fobo_break_detail", "arguments": {"break_id": "B-1"}}]
    h = FakeHarness(start=_running(), polls=[_completed(tool_calls=calls)], on_poll=peek)
    t = FakeTime()
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    assert out.error is None
    # Another DB session saw the row running while the step waited.
    assert seen == [("running", "h-1")]

    row = await _row()
    assert row.status == "completed" and row.finished_ts is not None
    assert row.response["output"]["summary"] == "all explained"
    token = h.starts[0]["mcp"]["token"]
    assert row.token_hash == repo.hash_token(token)
    assert row.request["mcp"]["token"] == "<redacted>"
    assert row.caller["staff_id"] == "p1"
    assert row.breaks["B-3"]["pattern_code"] == "LATE-BOOK"

    [call] = await _agent_calls()
    assert call.application_name == "agent"
    assert call.row_count == 3
    assert call.result_summary == "all explained"
    assert call.error_detail is None
    assert call.result_rows == calls
    assert call.validated_parameters["harness_session_id"] == "h-1"
    assert call.validated_parameters["status"] == "completed"
    assert call.validated_parameters["total_cost_usd"] == 0.12
    assert call.validated_parameters["num_turns"] == 9
    assert sorted(call.validated_parameters["breaks"]) == ["B-1", "B-2", "B-3"]


async def test_timeout_marks_the_row_failed():
    await _investigation()
    h = FakeHarness(start=_running(), polls=[_running()])
    t = FakeTime()
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    row = await _row()
    assert row.status == "failed" and "timed out" in row.error
    assert out.error == row.error
    [call] = await _agent_calls()
    assert call.error_detail == row.error and call.result_rows == []
    params = call.validated_parameters
    assert (params["status"], params["total_cost_usd"], params["num_turns"]) == ("failed", None, None)


async def test_harness_failure_marks_the_row_failed():
    await _investigation()
    h = FakeHarness(start=_running(), polls=[_failed()])
    t = FakeTime()
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    row = await _row()
    assert (row.status, row.error) == ("failed", "E42 — harness crashed")
    assert out.error == "E42 — harness crashed"


async def test_start_unavailable_marks_the_row_failed():
    await _investigation()
    h = FakeHarness(start_error="connection refused")
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    row = await _row()
    assert (row.status, row.error) == ("failed", "connection refused")
    assert out.error == "connection refused"


async def test_a_non_unavailable_start_error_fails_the_row_and_escalates():
    await _investigation()
    h = FakeHarness(start=_running(sid="x" * 200), polls=[_completed()])
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    row = await _row()
    assert row.status == "failed" and row.error
    assert out.rec_verdict is None and out.error == row.error


@pytest.mark.parametrize("bad", ["oops", {"tool": "x"}, None, 7])
async def test_malformed_tool_calls_do_not_break_recording(bad):
    await _investigation()
    h = FakeHarness(start=_completed())
    h._start.payload["tool_calls"] = bad
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    assert out.error is None
    [call] = await _agent_calls()
    assert call.result_rows == []


async def test_only_dict_tool_calls_become_rows():
    await _investigation()
    h = FakeHarness(start=_completed(tool_calls=[1, {"tool": "x", "arguments": {}}]))
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    assert out.error is None
    [call] = await _agent_calls()
    assert call.result_rows == [{"tool": "x", "arguments": {}}]
    assert (await _row()).status == "completed"


async def _seed_row(status, harness_session_id=None, response=None, error=None):
    await _investigation()
    async with get_session() as s:
        row = await repo.create(s, investigation_session_id=SID, token_hash="h", caller={},
                                business_date=date(2026, 8, 3), breaks=UNSETTLED, request={})
        row.status = status
        row.harness_session_id = harness_session_id
        row.response = response
        row.error = error
        await s.commit()


async def test_a_running_row_resumes_polling_without_a_second_start():
    await _seed_row("running", harness_session_id="h-old")
    open_during_poll = []
    s = None

    async def check_tx():
        open_during_poll.append(s.in_transaction())

    h = FakeHarness(polls=[_running("h-old"), _completed(sid="h-old")], on_poll=check_tx)
    t = FakeTime()
    async with get_session() as s:
        # The step has read from this session before, as reason() does.
        await repo.get_for_investigation(s, SID)
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h, sleep=t.sleep, clock=t.clock)
    # No transaction is held open while the step waits on the harness.
    assert open_during_poll == [False, False]
    assert h.starts == []
    assert h.polled == ["h-old", "h-old"]
    assert out.error is None and out.harness_session_id == "h-old"
    assert (await _row()).status == "completed"


async def test_a_completed_row_is_reused_and_recorded_once():
    await _investigation()
    t = FakeTime()
    async with get_session() as s:
        await run_agent(s, _state(), UNSETTLED, reasoner=FakeHarness(start=_completed()),
                        sleep=t.sleep, clock=t.clock)
    again = FakeHarness(start=_completed(), polls=[_completed()])
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=again, sleep=t.sleep, clock=t.clock)
    assert again.starts == [] and again.polled == []
    assert out.error is None and out.rec_verdict.summary == "all explained"
    assert out.harness_session_id == "h-1"
    assert len(await _agent_calls()) == 1


async def test_a_starting_row_escalates_without_starting():
    await _seed_row("starting")
    h = FakeHarness(start=_completed())
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    assert h.starts == [] and h.polled == []
    assert out.rec_verdict is None and "before the harness answered" in out.error
    assert (await _row()).status == "failed"


async def test_a_failed_row_escalates_with_its_stored_error():
    await _seed_row("failed", harness_session_id="h-x", error="E1 — earlier failure")
    h = FakeHarness(start=_completed())
    async with get_session() as s:
        out = await run_agent(s, _state(), UNSETTLED, reasoner=h)
    assert h.starts == []
    assert out.error == "E1 — earlier failure" and out.harness_session_id == "h-x"
    async with get_session() as s:
        n = await s.scalar(select(func.count()).select_from(SourceCall))
    assert n == 1
