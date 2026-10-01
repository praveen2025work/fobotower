from datetime import date

from fobo.contracts.models import CandidateCause
from fobo.contracts.models import PatternGroup
from fobo.reasoning.contracts import (
    BreakException, CheckPerformed, Classification, PatternVerdict, RecVerdict,
    Remediation, RootCause, SkillVerdict,
)
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable
from fobo.investigation.steps.reason import reason


def _pos(c):
    return CandidateCause(check_id=c, positive=True, description="d", supporting_ids=["B-1"])


def _neg(c):
    return CandidateCause(check_id=c, positive=False, description="d")


ALL = ("C1", "C2", "C3", "C4", "C5", "C6")


def _state(candidates, **brk_over):
    brk = {"break_id": "B-1", "book_ref": "PRIME-MB-01", "line_code": "CASH",
           "fo_value": 102340.0, "bo_value": 100000.0} | brk_over
    return {
        "breaks": [brk],
        "candidates": {"B-1": candidates},
        "deltas": {"B-1": 2340.0},
        "reasons": {"B-1": "Nostro statement received after 23:30 cutoff"},
        "business_date": date(2026, 8, 3),
        "evidence_gaps": [],
    }


class FakeHarness:
    """A rec-level port double: records every start, so a test can prove none
    happened; answers with a completed RecVerdict, a failure, or an outage."""

    name = "recording"

    def __init__(self, rec=None, fail=False, failed_error=None):
        self.calls = []
        self.polled = []
        self._rec = rec
        self._fail = fail
        self._failed_error = failed_error

    async def start(self, request):
        self.calls.append(request)
        if self._fail:
            raise ReasoningUnavailable("unavailable in test")
        if self._failed_error:
            return HarnessStatus(session_id="h-1", status="failed", error=self._failed_error)
        return HarnessStatus(session_id="h-1", status="completed", output=self._rec,
                             payload={"session_id": "h-1", "status": "completed"})

    async def poll(self, session_id):
        self.polled.append(session_id)
        raise AssertionError("a completed start is never polled")


def _fields(verdict="POST", side="BO", established=True):
    return dict(
        break_summary="s",
        checks_performed=[CheckPerformed(test_id="FO-3", checked="c", result="Fail", evidence="e")],
        root_cause=RootCause(established=established, statement="cause", side=side),
        classification=Classification(category_code="G", category_name="Corporate action break", deterministic=False),
        verdict=verdict,
        verdict_reason="r",
        remediation=Remediation(who_to_engage=["desk"], what_to_raise=["DQ"]),
        end_state_validation="open",
        requires_sme_review=True,
        competing_hypotheses=["h1", "h2"],
    )


def _verdict(verdict="POST", side="BO", established=True):
    return SkillVerdict(**_fields(verdict, side, established))


def _rec(*codes, verdict="POST", side="BO", established=True, exceptions=()):
    """A RecVerdict giving each named pattern the same verdict."""
    return RecVerdict(
        summary="agent summary",
        patterns=[PatternVerdict(pattern_code=c, **_fields(verdict, side, established))
                  for c in codes],
        exceptions=list(exceptions),
    )


async def test_a_single_cause_never_reaches_the_reasoner():
    """The orchestrator's point: what is codifiable costs no model call."""
    r = FakeHarness()
    out = await reason(_state([_pos("C1")] + [_neg(c) for c in ALL[1:]]), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["B-1"]["deterministic"] is True
    assert out["determinism"]["share"] == 1.0


async def test_a_missing_side_is_settled_without_the_reasoner():
    r = FakeHarness()
    out = await reason(_state([_neg(c) for c in ALL], bo_value=None), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["B-1"]["pattern"] == "missing_side"


async def test_a_motif_rejection_is_correct_and_repost_without_the_reasoner():
    r = FakeHarness()
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")],
                              motif_rejected=True), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["B-1"]["verdict"] == "CORRECT_AND_REPOST"


async def test_multiple_causes_go_to_the_reasoner():
    r = FakeHarness(rec=_rec("UNGROUPED"))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    assert len(r.calls) == 1
    assert out["findings"]["B-1"]["reasoner"] == "recording"
    assert out["determinism"]["escalated_to_reasoner"] == 1


async def test_the_reasoner_cannot_post_an_fo_side_cause():
    """R2 is graph code. A reasoner returning POST for an FO cause is
    corrected by construction."""
    r = FakeHarness(rec=_rec("UNGROUPED", verdict="POST", side="FO"))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    f = out["findings"]["B-1"]
    assert f["verdict"] == "DO_NOT_POST"
    assert f["verdict_proposed"] == "POST"
    assert f["verdict_overridden"] is True
    assert any("R2" in g for g in f["guard_reasons"])


async def test_the_reasoner_cannot_post_an_unevidenced_cause():
    r = FakeHarness(rec=_rec("UNGROUPED", verdict="POST", side="BO", established=False))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    assert out["findings"]["B-1"]["verdict"] == "ESCALATE"


async def test_an_unavailable_reasoner_escalates_and_flags_a_gap():
    r = FakeHarness(fail=True)
    out = await reason(_state([_neg(c) for c in ALL]), session=None, reasoner=r)
    f = out["findings"]["B-1"]
    assert f["verdict"] == "ESCALATE"
    assert f["established"] is False
    assert "reasoning:B-1" in out["evidence_gaps"]


async def test_a_reasoner_post_is_conditional_while_thresholds_are_unset():
    """P1: with no session the policy params are treated as unset."""
    r = FakeHarness(rec=_rec("UNGROUPED", verdict="POST", side="BO"))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    f = out["findings"]["B-1"]
    assert f["verdict"] == "POST"
    assert f["requires_controller_confirmation"] is True
    assert "materiality_threshold" in f["conditional_on"]


async def test_coverage_reports_the_share_that_needed_no_model():
    r = FakeHarness(fail=True)
    st = _state([_pos("C1")] + [_neg(c) for c in ALL[1:]])
    st["breaks"].append({"break_id": "B-2", "book_ref": "PRIME-MB-02",
                         "fo_value": 1.0, "bo_value": 0.0})
    st["candidates"]["B-2"] = [_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]
    st["deltas"]["B-2"] = 1.0
    out = await reason(st, session=None, reasoner=r)
    cov = out["determinism"]
    assert cov["total"] == 2
    assert cov["deterministic"] == 1
    assert cov["share"] == 0.5


# ---------- one agent session per L4 run ----------

MULTI = [_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]
NONE_FOUND = [_neg(c) for c in ALL]


def _rec_state(n_fx=7, n_late=2, settled=1):
    """Unsettled breaks in two pattern groups, plus some a rule settles."""
    breaks, candidates, deltas, groups = [], {}, {}, {"P-204": [], "LATE-BOOK": []}
    for i in range(n_fx):
        bid = f"FX-{i}"
        breaks.append({"break_id": bid, "book_ref": "MB", "fo_value": 1.0, "bo_value": 0.0})
        candidates[bid] = MULTI
        deltas[bid] = float(i + 1) * (-1 if i % 2 else 1)
        groups["P-204"].append(bid)
    for i in range(n_late):
        bid = f"LB-{i}"
        breaks.append({"break_id": bid, "book_ref": "MB", "fo_value": 1.0, "bo_value": 0.0})
        candidates[bid] = NONE_FOUND
        deltas[bid] = 100.0 + i
        groups["LATE-BOOK"].append(bid)
    for i in range(settled):
        bid = f"OK-{i}"
        breaks.append({"break_id": bid, "book_ref": "MB", "fo_value": 1.0, "bo_value": 0.0})
        candidates[bid] = [_pos("C1")] + [_neg(c) for c in ALL[1:]]
        deltas[bid] = 1.0
    return {
        "investigation_session_id": "sess-r-2031",
        "reconciliation_id": "R-2031",
        "master_book": "FICR-MB",
        "run_id": "run-1",
        "breaks": breaks,
        "candidates": candidates,
        "deltas": deltas,
        "reasons": {},
        "business_date": date(2026, 8, 3),
        "evidence_gaps": [],
        "book_resolutions": {"FX-0": "BOOK-9"},
        "pattern_groups": [
            PatternGroup(group_id=f"g:{c}", pattern_code=c, label=c.title(), mode="manual",
                         break_ids=ids)
            for c, ids in groups.items()
        ],
    }


async def test_no_unsettled_breaks_never_starts_a_session():
    r = FakeHarness()
    out = await reason(_rec_state(n_fx=0, n_late=0, settled=3), session=None, reasoner=r)
    assert r.calls == []
    assert out["reasoning_error"] is None


async def test_unsettled_breaks_make_exactly_one_session():
    r = FakeHarness(rec=_rec("P-204", "LATE-BOOK"))
    await reason(_rec_state(), session=None, reasoner=r)
    assert len(r.calls) == 1
    inputs = r.calls[0]["inputs"]
    assert inputs["already_established"] == {"total": 10, "settled_by_rules": 1, "unsettled": 9}
    fx, late = inputs["patterns"]
    assert (fx["pattern_code"], fx["break_count"], fx["total_amount"]) == ("P-204", 7, 28.0)
    assert (late["pattern_code"], late["break_count"], late["total_amount"]) == ("LATE-BOOK", 2, 201.0)
    assert len(fx["sample"]) == 5
    assert [s["break_id"] for s in fx["sample"]] == ["FX-6", "FX-5", "FX-4", "FX-3", "FX-2"]
    sample0 = next(s for s in fx["sample"] if s["break_id"] == "FX-6")
    assert sample0["pattern_code"] == "P-204"


async def test_a_pattern_verdict_applies_to_every_break_in_it():
    r = FakeHarness(rec=_rec("P-204", "LATE-BOOK"))
    out = await reason(_rec_state(), session=None, reasoner=r)
    for bid in [f"FX-{i}" for i in range(7)] + ["LB-0", "LB-1"]:
        f = out["findings"][bid]
        assert f["root_cause"] == "cause"
        assert f["verdict"] == "POST"
        assert f["deterministic"] is False and f["requires_sme_review"] is True
        assert f["reasoner"] == "recording"
        assert f["harness_session_id"] == "h-1"
    assert out["findings"]["FX-0"]["pattern_code"] == "P-204"
    assert out["findings"]["LB-0"]["pattern_code"] == "LATE-BOOK"
    assert out["findings"]["OK-0"]["deterministic"] is True
    assert out["reasoning_error"] is None


async def test_an_exception_overrides_its_patterns_verdict():
    exc = BreakException(break_id="FX-3", reason="odd one",
                         verdict=_verdict(verdict="ESCALATE", side="UNKNOWN", established=False))
    r = FakeHarness(rec=_rec("P-204", "LATE-BOOK", exceptions=[exc]))
    out = await reason(_rec_state(), session=None, reasoner=r)
    assert out["findings"]["FX-3"]["verdict"] == "ESCALATE"
    assert out["findings"]["FX-2"]["verdict"] == "POST"


async def test_a_break_the_agent_does_not_cover_escalates_with_a_gap():
    r = FakeHarness(rec=_rec("P-204"))
    out = await reason(_rec_state(), session=None, reasoner=r)
    f = out["findings"]["LB-0"]
    assert f["verdict"] == "ESCALATE"
    assert f["established"] is False and f["category_code"] == "H"
    assert "reasoning:LB-0" in out["evidence_gaps"]
    assert "reasoning:FX-0" not in out["evidence_gaps"]
    assert "LB-0" in out["reasoning_error"] and "LB-1" in out["reasoning_error"]


async def test_guards_still_override_the_agent():
    r = FakeHarness(rec=_rec("P-204", "LATE-BOOK", verdict="POST", side="FO"))
    out = await reason(_rec_state(), session=None, reasoner=r)
    f = out["findings"]["FX-0"]
    assert f["verdict"] != "POST"
    assert f["verdict_proposed"] == "POST" and f["verdict_overridden"] is True


async def test_a_failed_harness_escalates_every_unsettled_break():
    r = FakeHarness(failed_error="E42 — harness crashed")
    out = await reason(_rec_state(), session=None, reasoner=r)
    assert out["reasoning_error"] == "E42 — harness crashed"
    assert out["findings"]["FX-0"]["verdict"] == "ESCALATE"
    assert "reasoning:LB-1" in out["evidence_gaps"]
    assert out["findings"]["OK-0"]["deterministic"] is True


async def test_no_reasoner_configured_is_unchanged(monkeypatch):
    """reasoner: none — the default — escalates exactly as before."""
    monkeypatch.delenv("FOBO_REASONER", raising=False)
    out = await reason(_state(NONE_FOUND), session=None)
    f = out["findings"]["B-1"]
    assert f["verdict"] == "ESCALATE"
    assert f["reasoner"] == "none"
    assert "harness_session_id" not in f
    assert "reasoning:B-1" in out["evidence_gaps"]
    assert out["reasoning_error"].startswith("no reasoner configured")


async def test_no_reasoner_leaves_no_agent_session_or_source_call(monkeypatch):
    """With a database too: no agent_session row, no agent.session call."""
    from sqlalchemy import func, select

    from fobo.db.base import get_session
    from fobo.db.models_ops import SourceCall
    from fobo.db.models_session import AgentSession

    monkeypatch.delenv("FOBO_REASONER", raising=False)
    async with get_session() as s:
        out = await reason(_rec_state(), session=s)
        assert out["findings"]["FX-0"]["verdict"] == "ESCALATE"
        for model in (AgentSession, SourceCall):
            assert await s.scalar(select(func.count()).select_from(model)) == 0


async def test_uncovered_breaks_are_counted_and_capped_at_ten_ids():
    from fobo.investigation.steps.reason import _uncovered_error

    ids = [f"B-{i}" for i in range(25)]
    msg = _uncovered_error(ids)
    assert msg.startswith("25 breaks not covered by the agent's response (")
    assert "B-9" in msg and "B-10" not in msg
    assert msg.endswith("and 15 more)")
    assert _uncovered_error(["B-1", "B-2"]) == "2 breaks not covered by the agent's response (B-1, B-2)"
