from datetime import date

import pytest

from app.contracts.models import CandidateCause
from app.reasoning.client import ReasoningUnavailable
from app.workflow.nodes.reason import CHECK_TO_CATEGORY, reason


def _pos(check_id):
    return CandidateCause(
        check_id=check_id, positive=True, description="d", supporting_ids=["b-01"]
    )


def _neg(check_id):
    return CandidateCause(check_id=check_id, positive=False, description="d")


def _state(candidates):
    return {
        "breaks": [{"break_id": "b-01", "book_ref": "APAC-CASH-01", "line_code": "CASH"}],
        "candidates": {"b-01": candidates},
        "deltas": {"b-01": 2340.0},
        "reasons": {"b-01": "Nostro statement received after 23:30 cutoff"},
        "business_date": date(2026, 8, 3),
        "evidence_gaps": [],
    }


async def test_a_single_cause_applies_the_rule_and_skips_the_model():
    """R7: deterministic breaks are ~80% of the population. Paying a model to
    restate a codified rule adds cost, latency and variance for nothing."""
    candidates = [_pos("C1")] + [_neg(c) for c in ("C2", "C3", "C4", "C5", "C6")]
    out = await reason(_state(candidates), session=None)
    finding = out["findings"]["b-01"]
    assert finding["deterministic"] is True
    assert finding["rule_applied"] == "C1"
    assert finding["requires_sme_review"] is False
    assert finding["established"] is True


async def test_the_rule_maps_to_the_skills_break_classification():
    for check, category in CHECK_TO_CATEGORY.items():
        candidates = [_pos(check)] + [
            _neg(c) for c in ("C1", "C2", "C3", "C4", "C5", "C6") if c != check
        ]
        out = await reason(_state(candidates), session=None)
        assert out["findings"]["b-01"]["category_code"] == category


async def test_multiple_causes_route_to_the_model(monkeypatch):
    """The skill's ~20%: multiple simultaneous root causes need judgement."""
    seen = {}

    async def fake(record):
        seen["record"] = record
        raise ReasoningUnavailable("no credential in test")

    monkeypatch.setattr("app.workflow.nodes.reason.reason_over_break", fake)
    candidates = [_pos("C1"), _pos("C5")] + [
        _neg(c) for c in ("C2", "C3", "C4", "C6")
    ]
    await reason(_state(candidates), session=None)
    assert seen["record"]["break_id"] == "b-01"
    assert len(seen["record"]["checks"]) == 6


async def test_no_cause_at_all_is_also_judgement_based(monkeypatch):
    called = {"n": 0}

    async def fake(record):
        called["n"] += 1
        raise ReasoningUnavailable("no credential in test")

    monkeypatch.setattr("app.workflow.nodes.reason.reason_over_break", fake)
    candidates = [_neg(c) for c in ("C1", "C2", "C3", "C4", "C5", "C6")]
    await reason(_state(candidates), session=None)
    assert called["n"] == 1


async def test_reasoning_unavailable_escalates_rather_than_guessing(monkeypatch):
    """R6: unknown root cause is an escalation outcome, not a posting one.
    A silent fallback to the deterministic guess would assert a cause the
    evidence does not support."""

    async def fake(record):
        raise ReasoningUnavailable("no ANTHROPIC_API_KEY")

    monkeypatch.setattr("app.workflow.nodes.reason.reason_over_break", fake)
    candidates = [_pos("C1"), _pos("C5")] + [
        _neg(c) for c in ("C2", "C3", "C4", "C6")
    ]
    out = await reason(_state(candidates), session=None)
    finding = out["findings"]["b-01"]
    assert finding["verdict"] == "ESCALATE"
    assert finding["established"] is False
    assert finding["requires_sme_review"] is True
    assert "reasoning:b-01" in out["evidence_gaps"]
    assert out["reasoning_error"]


async def test_the_model_sees_priors_and_lineage_as_evidence(monkeypatch):
    seen = {}

    async def fake(record):
        seen["record"] = record
        raise ReasoningUnavailable("x")

    monkeypatch.setattr("app.workflow.nodes.reason.reason_over_break", fake)
    st = _state([_pos("C1"), _pos("C5")] + [_neg(c) for c in ("C2", "C3", "C4", "C6")])
    st["priors"] = {"b-01": [{"break_id": "p1", "outcome": "approved"}]}
    st["lineage"] = {"b-01": [{"natural_key": "APAC-CASH"}]}
    await reason(st, session=None)
    assert seen["record"]["prior_resolutions"]
    assert seen["record"]["lineage"]


def test_the_skill_document_is_the_system_prompt():
    """If the skill file moves or is emptied, reasoning must fail loudly."""
    from app.reasoning.client import skill_text

    text = skill_text()
    assert "FO PnL = BO PnL" in text
    assert "R2" in text and "Never assume Front Office is correct" in text
    assert "DO NOT POST" in text


def test_a_missing_credential_raises_rather_than_returning_none():
    from app.reasoning.client import build_client, credentials_available

    if credentials_available():
        pytest.skip("credentials present in this environment")
    with pytest.raises(ReasoningUnavailable):
        build_client()
