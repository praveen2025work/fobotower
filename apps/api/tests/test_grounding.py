from datetime import date

from sqlalchemy import func, select

from app.contracts.models import Caller
from app.db.base import get_session
from app.db.models_ops import SourceCall
from app.grounding.recorder import GroundingRecorder, calls_for
from app.workflow.nodes.gather import gather
from app.workflow.nodes.resolve import resolve
from app.workflow.session import ensure_investigation_session
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
SID = "sess-ground"


def _brk(**over):
    return {
        "break_id": "b-01",
        "book_ref": "APAC-CASH-01",
        "line_code": "CASH",
        "fo_value": 102340.0,
        "bo_value": 100000.0,
    } | over


def _state(breaks):
    return {
        "investigation_session_id": SID,
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


async def _prepare(s, breaks=None):
    await load_all(s)
    st = _state(breaks if breaks is not None else [_brk()])
    await ensure_investigation_session(s, st)
    return st


async def test_recorder_writes_a_row_with_its_result_summary():
    async with get_session() as s:
        st = await _prepare(s)
        rec = GroundingRecorder(s, st["investigation_session_id"])
        await rec.record(
            application="CATS",
            tool="CATS.getCashMovements",
            params={"book": "APAC-CASH", "valueDate": "2026-08-03"},
            row_count=312,
            summary="312 movements",
        )
        await s.commit()
        row = await s.scalar(select(SourceCall))
        assert row.application_name == "CATS"
        assert row.row_count == 312
        assert row.result_summary == "312 movements"
        assert row.entitlement_result == "allowed"


async def test_gather_records_one_call_per_retrieval():
    """The Grounding panel counts these. If gather retrieves and does not
    record, the panel undercounts and the audit record is incomplete."""
    async with get_session() as s:
        st = await _prepare(s)
        st |= await resolve(st, session=s)
        await gather(st, session=s)
        await s.commit()
        n = await s.scalar(select(func.count()).select_from(SourceCall))
        assert n >= 4, f"expected breaks, lineage, priors and movements; got {n}"


async def test_gather_records_the_applications_the_mock_names():
    async with get_session() as s:
        st = await _prepare(s)
        st |= await resolve(st, session=s)
        await gather(st, session=s)
        await s.commit()
        apps = {r["application"] for r in await calls_for(s, SID)}
        assert {"RecFactory", "CATS", "MOTIF"} <= apps


async def test_a_failed_retrieval_is_recorded_as_failed_not_omitted():
    """A source failure must be visible. Dropping the row hides it."""
    from app.graph.repository import GraphRepository

    async def boom(*args, **kwargs):
        raise TimeoutError("prior store unavailable")

    async with get_session() as s:
        st = await _prepare(s)
        original = GraphRepository.similar_breaks
        GraphRepository.similar_breaks = boom
        try:
            st |= await resolve(st, session=s)
            await gather(st, session=s)
            await s.commit()
        finally:
            GraphRepository.similar_breaks = original

        failed = [r for r in await calls_for(s, SID) if r["error"]]
        assert failed, "the failed priors lookup was not recorded"
        assert failed[0]["entitlement_result"] != "denied"
        assert failed[0]["row_count"] is None


async def test_calls_are_returned_in_call_order():
    async with get_session() as s:
        st = await _prepare(s)
        rec = GroundingRecorder(s, SID)
        for i in range(3):
            await rec.record(
                application="MOTIF",
                tool=f"tool-{i}",
                params={},
                row_count=i,
                summary=f"{i} rows",
            )
        await s.commit()
        summaries = [r["summary"] for r in await calls_for(s, SID)]
        assert summaries == ["0 rows", "1 rows", "2 rows"]
