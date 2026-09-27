"""apply_decision: record one controller decision and set its breaks' outcomes.

No longer its own route — the classic action/group_id/break_id request body
is dropped (spec §5); the console reaches this logic through
`POST /api/recs/{id}/decisions` with the {ids, decision} shape instead (see
test_console_actions.py, which already covers most of this through that route).
apply_decision's group_id and single-break_id paths were pruned along with
it (the only caller always sends break_ids — see fobo/web/decisions.py), so this
file only exercises the break_ids path, directly rather than through HTTP:
it can construct a case that isn't drafted for R-1055's real pattern groups
(the "unknown break" case) more simply than the HTTP layer allows.
"""

import pytest
from fastapi import HTTPException

from fobo.web.investigations import open_investigation, rec_and_run
from fobo.web.decisions import DecisionRequest, apply_decision
from fobo.web.dependencies import ensure_seed_data
from fobo.db.base import get_session
from seed_data.history import COB

# R-1055's P-204 group (FX timing lag) — see test_console_board.py and
# test_console_actions.py, which approve the same six breaks as one decision.
P204_BREAKS = ["B-1", "B-2", "B-3", "B-4", "B-5", "B-6"]


async def _open_r1055():
    """Opening the case seeds fixtures and runs the investigation."""
    async with get_session() as s:
        await ensure_seed_data(s)
        rec, run = await rec_and_run(s, "R-1055", COB)
        await open_investigation(s, rec, run)


async def _decide(body: DecisionRequest, key: str, rec_id: str = "R-1055") -> dict:
    async with get_session() as s:
        return await apply_decision(s, rec_id, body, key)


async def test_approving_several_breaks_resolves_them_all():
    await _open_r1055()
    result = await _decide(DecisionRequest(action="approve", break_ids=P204_BREAKS), "k-approve-1")
    assert result["break_ids"] == P204_BREAKS


async def test_a_repeated_idempotency_key_is_rejected():
    await _open_r1055()
    body = DecisionRequest(action="approve", break_ids=P204_BREAKS)
    await _decide(body, "k-dup")
    with pytest.raises(HTTPException) as exc:
        await _decide(body, "k-dup")
    assert exc.value.status_code == 409


async def test_a_rejection_without_a_reason_is_refused():
    """An empty rejection gives the retry cycle nothing to correct."""
    await _open_r1055()
    with pytest.raises(HTTPException) as exc:
        await _decide(DecisionRequest(action="reject", break_ids=P204_BREAKS), "k-noreason")
    assert exc.value.status_code == 422


async def test_a_rejection_with_a_reason_is_accepted():
    await _open_r1055()
    result = await _decide(
        DecisionRequest(action="reject", break_ids=P204_BREAKS, reason="Amount unverified"),
        "k-reason",
    )
    assert result["action"] == "reject"


async def test_a_single_break_can_be_decided():
    await _open_r1055()
    result = await _decide(DecisionRequest(action="approve", break_ids=["B-1"]), "k-one")
    assert result["break_ids"] == ["B-1"]


async def test_a_break_not_drafted_in_the_case_is_404():
    await _open_r1055()
    with pytest.raises(HTTPException) as exc:
        await _decide(DecisionRequest(action="approve", break_ids=["NOPE"]), "k-unknown")
    assert exc.value.status_code == 404
