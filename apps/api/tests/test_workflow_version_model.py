"""The database itself guarantees one active workflow version."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import get_session
from app.db.models_workflow import WorkflowVersion


def _row(number: int, status: str, **kw) -> WorkflowVersion:
    return WorkflowVersion(
        number=number, config={"steps": []}, status=status, note="n",
        drafted_by="praveen", drafted_at=datetime.now(timezone.utc), **kw,
    )


async def test_a_version_round_trips():
    async with get_session() as s:
        s.add(_row(1, "active"))
        await s.commit()
    async with get_session() as s:
        got = await s.get(WorkflowVersion, 1)
        assert got.status == "active" and got.config == {"steps": []}


async def test_the_database_refuses_a_second_active_version():
    async with get_session() as s:
        s.add(_row(1, "active"))
        await s.commit()
        s.add(_row(2, "active"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_any_number_of_drafts_may_coexist():
    async with get_session() as s:
        s.add_all([_row(1, "active"), _row(2, "draft", based_on=1), _row(3, "draft", based_on=1)])
        await s.commit()


async def test_an_unknown_status_is_refused():
    async with get_session() as s:
        s.add(_row(1, "live"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_a_decision_key_is_used_once():
    async with get_session() as s:
        s.add_all([_row(1, "superseded", decision_key="k"), _row(2, "active", decision_key="k")])
        with pytest.raises(IntegrityError):
            await s.commit()
