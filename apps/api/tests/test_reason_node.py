from datetime import date

from app.contracts.models import CandidateCause
from app.reasoning.contracts import (
    CheckPerformed, Classification, Remediation, RootCause, SkillVerdict,
)
from app.reasoning.port import ReasoningUnavailable
from app.workflow.nodes.reason import reason


def _pos(c):
    return CandidateCause(check_id=c, positive=True, description="d", supporting_ids=["b-01"])


def _neg(c):
    return CandidateCause(check_id=c, positive=False, description="d")


ALL = ("C1", "C2", "C3", "C4", "C5", "C6")


def _state(candidates, **brk_over):
    brk = {"break_id": "b-01", "book_ref": "APAC-CASH-01", "line_code": "CASH",
           "fo_value": 102340.0, "bo_value": 100000.0} | brk_over
    return {
        "breaks": [brk],
        "candidates": {"b-01": candidates},
        "deltas": {"b-01": 2340.0},
        "reasons": {"b-01": "Nostro statement received after 23:30 cutoff"},
        "business_date": date(2026, 8, 3),
        "evidence_gaps": [],
    }


class Recording:
    """A reasoner that records every call, so a test can prove none happened."""

    name = "recording"

    def __init__(self, verdict=None, fail=False):
        self.calls = []
        self._verdict = verdict
        self._fail = fail

    async def investigate(self, evidence):
        self.calls.append(evidence)
        if self._fail:
            raise ReasoningUnavailable("unavailable in test")
        return self._verdict


def _verdict(verdict="POST", side="BO", established=True):
    return SkillVerdict(
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


async def test_a_single_cause_never_reaches_the_reasoner():
    """The orchestrator's point: what is codifiable costs no model call."""
    r = Recording()
    out = await reason(_state([_pos("C1")] + [_neg(c) for c in ALL[1:]]), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["b-01"]["deterministic"] is True
    assert out["determinism"]["share"] == 1.0


async def test_a_missing_side_is_settled_without_the_reasoner():
    r = Recording()
    out = await reason(_state([_neg(c) for c in ALL], bo_value=None), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["b-01"]["pattern"] == "missing_side"


async def test_a_motif_rejection_is_correct_and_repost_without_the_reasoner():
    r = Recording()
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")],
                              motif_rejected=True), session=None, reasoner=r)
    assert r.calls == []
    assert out["findings"]["b-01"]["verdict"] == "CORRECT_AND_REPOST"


async def test_multiple_causes_go_to_the_reasoner():
    r = Recording(verdict=_verdict())
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    assert len(r.calls) == 1
    assert out["findings"]["b-01"]["reasoner"] == "recording"
    assert out["determinism"]["escalated_to_reasoner"] == 1


async def test_the_reasoner_cannot_post_an_fo_side_cause():
    """R2 is graph code. A reasoner returning POST for an FO cause is
    corrected by construction."""
    r = Recording(verdict=_verdict(verdict="POST", side="FO"))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    f = out["findings"]["b-01"]
    assert f["verdict"] == "DO_NOT_POST"
    assert f["verdict_proposed"] == "POST"
    assert f["verdict_overridden"] is True
    assert any("R2" in g for g in f["guard_reasons"])


async def test_the_reasoner_cannot_post_an_unevidenced_cause():
    r = Recording(verdict=_verdict(verdict="POST", side="BO", established=False))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    assert out["findings"]["b-01"]["verdict"] == "ESCALATE"


async def test_an_unavailable_reasoner_escalates_and_flags_a_gap():
    r = Recording(fail=True)
    out = await reason(_state([_neg(c) for c in ALL]), session=None, reasoner=r)
    f = out["findings"]["b-01"]
    assert f["verdict"] == "ESCALATE"
    assert f["established"] is False
    assert "reasoning:b-01" in out["evidence_gaps"]


async def test_a_reasoner_post_is_conditional_while_thresholds_are_unset():
    """P1: with no session the policy params are treated as unset."""
    r = Recording(verdict=_verdict(verdict="POST", side="BO"))
    out = await reason(_state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]),
                       session=None, reasoner=r)
    f = out["findings"]["b-01"]
    assert f["verdict"] == "POST"
    assert f["requires_controller_confirmation"] is True
    assert "materiality_threshold" in f["conditional_on"]


async def test_coverage_reports_the_share_that_needed_no_model():
    r = Recording(fail=True)
    st = _state([_pos("C1")] + [_neg(c) for c in ALL[1:]])
    st["breaks"].append({"break_id": "b-02", "book_ref": "APAC-CASH-02",
                         "fo_value": 1.0, "bo_value": 0.0})
    st["candidates"]["b-02"] = [_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")]
    st["deltas"]["b-02"] = 1.0
    out = await reason(st, session=None, reasoner=r)
    cov = out["determinism"]
    assert cov["total"] == 2
    assert cov["deterministic"] == 1
    assert cov["share"] == 0.5
