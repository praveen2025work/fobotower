from datetime import date

import pytest

from app.contracts.models import Caller
from app.db.base import get_session
from app.graph.repository import GraphRepository
from app.workflow.nodes.escalate import escalate
from app.workflow.nodes.gather import gather
from app.workflow.nodes.resolve import resolve
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")


def _state(breaks):
    return {
        "investigation_session_id": "sess-1",
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": FO,
        "breaks": breaks,
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }


def _brk(**over):
    base = {
        "break_id": "b-01",
        "book_ref": "APAC-CASH-01",
        "line_code": "CASH",
        "fo_value": 102340.0,
        "bo_value": 100000.0,
    }
    return base | over


async def test_resolve_pins_as_of_to_the_business_date():
    async with get_session() as s:
        await load_all(s)
        st = _state([_brk()])
        out = await resolve(st, session=s)
        assert out["book_resolutions"]["b-01"] == "book:APAC-CASH-01"
        assert out["as_of"] == date(2026, 8, 3)


async def test_resolve_escalates_an_unresolvable_book():
    async with get_session() as s:
        await load_all(s)
        st = _state([_brk(break_id="b-x", book_ref="NOPE-01")])
        out = await resolve(st, session=s)
        assert out["outcome"] == "escalated"
        assert out["escalation_reason"] == "UNRESOLVED_BOOK"


async def test_gather_returns_all_six_candidates_per_break():
    async with get_session() as s:
        await load_all(s)
        st = _state([_brk()])
        st |= await resolve(st, session=s)
        out = await gather(st, session=s)
        assert len(out["candidates"]["b-01"]) == 6


async def test_gather_computes_the_delta():
    async with get_session() as s:
        await load_all(s)
        st = _state([_brk()])
        st |= await resolve(st, session=s)
        out = await gather(st, session=s)
        assert out["deltas"]["b-01"] == pytest.approx(2340.0)


async def test_gather_escalates_when_the_delta_is_unavailable():
    """Nothing to explain without a delta."""
    async with get_session() as s:
        await load_all(s)
        st = _state([_brk(fo_value=None)])
        st |= await resolve(st, session=s)
        out = await gather(st, session=s)
        assert out["outcome"] == "escalated"
        assert out["escalation_reason"] == "DELTA_UNAVAILABLE"


async def test_gather_degrades_when_priors_are_unavailable(monkeypatch):
    """A failed priors lookup flags an evidence gap. It does not escalate,
    and it does not fabricate priors."""

    async def boom(*args, **kwargs):
        raise TimeoutError("prior store unavailable")

    monkeypatch.setattr(GraphRepository, "similar_breaks", boom)

    async with get_session() as s:
        await load_all(s)
        st = _state([_brk()])
        st |= await resolve(st, session=s)
        out = await gather(st, session=s)
        assert "priors:b-01" in out["evidence_gaps"]
        assert out.get("outcome") != "escalated"
        assert out["priors"]["b-01"] == []


async def test_escalate_rejects_an_unknown_reason_code():
    with pytest.raises(ValueError):
        await escalate({"escalation_reason": "SOMETHING_MADE_UP"})
