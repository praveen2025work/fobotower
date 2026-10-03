"""The agent_session table: one row per L4 agent run, found again by token.

The repository does not commit, so each test commits itself; the unique
constraint on investigation_session_id is what makes a restart pick up the
existing row instead of starting a second agent.
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from fobo.db.base import get_session
from fobo.db.models_session import InvestigationSession
from fobo.reasoning import agent_sessions as repo

SID = "sess-agent"
CALLER = {"staff_id": "p1", "roles": ["FO"], "entity_scope": ["LE-APAC-01"], "region": "APAC"}


async def _investigation(s, sid=SID):
    s.add(
        InvestigationSession(
            investigation_session_id=sid,
            reconciliation_id="R-1055",
            master_book="APAC-CASH",
            business_date=date(2026, 8, 3),
            run_id="run-1100",
            status="analysing",
        )
    )
    await s.flush()


async def _create(s, sid=SID, token_hash="h"):
    return await repo.create(
        s,
        investigation_session_id=sid,
        token_hash=token_hash,
        caller=CALLER,
        business_date=date(2026, 8, 3),
        breaks={"ids": ["B-1"]},
        request={"q": "why"},
    )


def test_new_token_pairs_with_its_hash_and_differs_per_call():
    token, digest = repo.new_token()
    assert repo.hash_token(token) == digest
    assert len(digest) == 64
    assert repo.new_token()[0] != token


async def test_create_starts_with_id_and_status():
    async with get_session() as s:
        await _investigation(s)
        row = await _create(s)
        await s.commit()
        assert row.agent_session_id == f"{SID}:agent"
        assert row.status == "starting"
        assert row.finished_ts is None
        assert (await repo.get_for_investigation(s, SID)).agent_session_id == row.agent_session_id
        assert await repo.get_for_investigation(s, "nope") is None


async def test_transitions_set_status_and_finished_ts():
    async with get_session() as s:
        await _investigation(s)
        row = await _create(s)
        await repo.mark_running(s, row, "harness-1")
        assert (row.status, row.harness_session_id, row.finished_ts) == ("running", "harness-1", None)
        await repo.mark_completed(s, row, {"ok": True})
        assert row.status == "completed" and row.response == {"ok": True}
        assert row.finished_ts is not None
        await s.commit()

    async with get_session() as s:
        await _investigation(s, "sess-2")
        row = await _create(s, "sess-2", "h2")
        await repo.mark_failed(s, row, "boom")
        assert row.status == "failed" and row.error == "boom"
        assert row.response is None and row.finished_ts is not None
        await repo.mark_failed(s, row, "again", {"partial": 1})
        assert row.response == {"partial": 1}


async def test_find_active_by_token():
    token, digest = repo.new_token()
    async with get_session() as s:
        await _investigation(s)
        row = await _create(s, token_hash=digest)
        assert (await repo.find_active_by_token(s, token)).agent_session_id == row.agent_session_id
        await repo.mark_running(s, row, "h")
        assert await repo.find_active_by_token(s, token) is not None
        assert await repo.find_active_by_token(s, "wrong") is None
        await repo.mark_completed(s, row, {})
        assert await repo.find_active_by_token(s, token) is None


async def test_a_row_older_than_the_session_window_is_not_active():
    from datetime import datetime, timedelta, timezone

    from fobo.investigation.settings import settings

    window = settings().session_service.max_wait_seconds + 300
    token, digest = repo.new_token()
    async with get_session() as s:
        await _investigation(s)
        row = await _create(s, token_hash=digest)
        await repo.mark_running(s, row, "h")
        row.created_ts = datetime.now(timezone.utc) - timedelta(seconds=window - 30)
        await s.flush()
        assert await repo.find_active_by_token(s, token) is not None
        row.created_ts = datetime.now(timezone.utc) - timedelta(seconds=window + 30)
        await s.flush()
        assert await repo.find_active_by_token(s, token) is None


async def test_failed_row_is_not_active():
    token, digest = repo.new_token()
    async with get_session() as s:
        await _investigation(s)
        row = await _create(s, token_hash=digest)
        await repo.mark_failed(s, row, "x")
        assert await repo.find_active_by_token(s, token) is None


async def test_second_create_for_same_investigation_is_rejected():
    async with get_session() as s:
        await _investigation(s)
        await _create(s)
        await s.commit()
        with pytest.raises(IntegrityError):
            await _create(s, token_hash="other")
            await s.flush()
