"""Deterministic verdicts come from the playbook, not from code."""

from datetime import date

from app.contracts.models import CandidateCause
from app.db.base import get_session
from app.playbook.loader import load_playbook
from app.workflow.nodes.reason import reason

ALL = ("C1", "C2", "C3", "C4", "C5", "C6")


def _only(check):
    return [CandidateCause(check_id=c, positive=(c == check), description="d",
                           supporting_ids=["b-01"] if c == check else []) for c in ALL]


def _state(check):
    return {
        "breaks": [{"break_id": "b-01", "book_ref": "APAC-CASH-01", "line_code": "CASH",
                    "fo_value": 102340.0, "bo_value": 100000.0}],
        "candidates": {"b-01": _only(check)},
        "deltas": {"b-01": 2340.0},
        "reasons": {"b-01": "r"},
        "business_date": date(2026, 8, 3),
        "evidence_gaps": [],
    }


class NoCalls:
    name = "should-not-be-called"

    async def investigate(self, evidence):
        raise AssertionError("a deterministic break reached the reasoner")


async def _finding(check):
    async with get_session() as s:
        await load_playbook(s)
        out = await reason(_state(check), session=s, reasoner=NoCalls())
        return out["findings"]["b-01"]


async def test_a_bo_side_redemption_break_posts():
    """C1: late nostro, BO timing -> category C, BO -> POST (the mock's
    'P-204 auto, approve all')."""
    f = await _finding("C1")
    assert f["verdict"] == "POST"
    assert f["side"] == "BO"
    assert f["category_code"] == "C"


async def test_a_static_data_break_does_not_post():
    """C2 -> category F -> DO_NOT_POST on either side (skill §8 static outlier)."""
    assert (await _finding("C2"))["verdict"] == "DO_NOT_POST"


async def test_an_fo_side_booking_break_does_not_post():
    """C5: pending desk confirmation, FO side -> DO_NOT_POST (R2)."""
    f = await _finding("C5")
    assert f["verdict"] == "DO_NOT_POST"
    assert f["side"] == "FO"


async def test_a_check_that_cannot_name_the_wrong_side_is_not_deterministic():
    """C3 proves the curves differ, not which one is wrong. R2 forbids
    assuming FO is right, so it must not be settled by rule."""
    async with get_session() as s:
        await load_playbook(s)
        out = await reason(_state("C3"), session=s)  # default reasoner: none
    f = out["findings"]["b-01"]
    assert f["deterministic"] is False
    assert f["verdict"] == "ESCALATE"


async def test_a_playbook_post_is_conditional_while_thresholds_are_unset():
    f = await _finding("C1")
    assert f["requires_controller_confirmation"] is True
    assert "materiality_threshold" in f["conditional_on"]


async def test_every_finding_records_the_playbook_version():
    assert (await _finding("C1"))["playbook_version"] == "1.0"
