"""apply_decision: record one controller decision and set its breaks' outcomes.

No longer its own route — the classic action/group_id/break_id request body
is dropped (spec §5); the console reaches this logic through
`POST /api/recs/{id}/decisions` with the {ids, decision} shape instead (see
test_helix_actions.py). Exercised directly here so the group_id and
single-break paths, which that shape cannot express, keep their coverage.
"""

import pytest
from fastapi import HTTPException

from api.cases import open_case, rec_and_run
from api.decisions import DecisionRequest, apply_decision
from api.deps import ensure_fixtures
from app.db.base import get_session
from fixtures.history import COB


async def _snapshot():
    async with get_session() as s:
        await ensure_fixtures(s)
        rec, run = await rec_and_run(s, "R-1055", COB)
        return await open_case(s, rec, run)


async def _group_id(code="P-204"):
    snapshot = await _snapshot()
    return next(g.group_id for g in snapshot.values["pattern_groups"] if g.pattern_code == code)


async def _decide(body: DecisionRequest, key: str, rec_id: str = "R-1055") -> dict:
    async with get_session() as s:
        return await apply_decision(s, rec_id, body, key)


async def test_approving_a_group_resolves_every_break_in_it():
    await _snapshot()  # opening the case seeds fixtures and runs the investigation
    gid = await _group_id()
    result = await _decide(DecisionRequest(action="approve", group_id=gid), "k-approve-1")
    assert len(result["break_ids"]) == 6


async def test_a_repeated_idempotency_key_is_rejected():
    await _snapshot()
    gid = await _group_id()
    body = DecisionRequest(action="approve", group_id=gid)
    await _decide(body, "k-dup")
    with pytest.raises(HTTPException) as exc:
        await _decide(body, "k-dup")
    assert exc.value.status_code == 409


async def test_a_rejection_without_a_reason_is_refused():
    """An empty rejection gives the retry cycle nothing to correct."""
    await _snapshot()
    gid = await _group_id()
    with pytest.raises(HTTPException) as exc:
        await _decide(DecisionRequest(action="reject", group_id=gid), "k-noreason")
    assert exc.value.status_code == 422


async def test_a_rejection_with_a_reason_is_accepted():
    await _snapshot()
    gid = await _group_id()
    result = await _decide(
        DecisionRequest(action="reject", group_id=gid, reason="Amount unverified"), "k-reason"
    )
    assert result["action"] == "reject"


async def test_a_single_break_can_be_decided():
    await _snapshot()
    result = await _decide(DecisionRequest(action="approve", break_id="B-1"), "k-one")
    assert result["break_ids"] == ["B-1"]


async def test_an_unknown_group_is_404():
    await _snapshot()
    with pytest.raises(HTTPException) as exc:
        await _decide(DecisionRequest(action="approve", group_id="nope"), "k-unknown")
    assert exc.value.status_code == 404


async def test_a_decision_with_neither_group_nor_break_is_refused():
    await _snapshot()
    with pytest.raises(HTTPException) as exc:
        await _decide(DecisionRequest(action="approve"), "k-empty")
    assert exc.value.status_code == 422
