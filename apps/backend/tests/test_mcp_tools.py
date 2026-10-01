"""The MCP tools: read-only graph lookups scoped to one agent session.

Each tool is plain async Python over an AgentContext; HTTP comes later. The
audit wrapper is what puts every call in the console's data panel.
"""

from datetime import date

import pytest
from sqlalchemy import select

from fobo.contracts.models import Caller
from fobo.db.base import get_session
from fobo.db.models_graph import BreakEvent
from fobo.db.models_ops import SourceCall
from fobo.db.models_session import InvestigationSession
from fobo.mcp_server import tools
from fobo.mcp_server.audit import audited
from fobo.mcp_server.context import AgentContext, context_for_token
from fobo.mcp_server.tools import ToolInputError
from fobo.reasoning import agent_sessions as sessions
from fobo.playbook.loader import load_playbook
from seed_data.loader import load_all

D = date(2026, 8, 3)
FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
OUTSIDER = Caller(staff_id="p2", roles=["FO"], entity_scope=["LE-EMEA-01"], region="EMEA")


def _brk(i: int, pattern: str = "P-204", book_id: str | None = "book:PRIME-MB-01") -> dict:
    return {
        "break_id": f"B-{i:03d}", "book": "PRIME-MB-01", "line_code": "CASH",
        "cob_date": "2026-08-03", "fo_value": 1.0, "bo_value": 2.0, "break_amount": -1.0,
        "checks": [], "prior_resolutions": [], "lineage": [],
        "pattern_code": pattern, "book_id": book_id,
    }


def _ctx(caller: Caller = FO, breaks: dict | None = None) -> AgentContext:
    return AgentContext(
        investigation_session_id="sess-tools",
        caller=caller,
        business_date=D,
        breaks=breaks if breaks is not None else {"B-001": _brk(1)},
    )


async def _seeded(s):
    await load_all(s)
    await load_playbook(s)


async def test_list_tests_by_side():
    async with get_session() as s:
        await _seeded(s)
        out = await tools.fobo_list_tests(s, _ctx(), side="FO")
        assert [t["test_id"] for t in out["tests"]] == [f"FO-{i}" for i in range(1, 9)]


async def test_list_tests_rejects_bad_side():
    async with get_session() as s:
        await _seeded(s)
        with pytest.raises(ToolInputError):
            await tools.fobo_list_tests(s, _ctx(), side="XX")


async def test_evidence_required_for_fo6():
    async with get_session() as s:
        await _seeded(s)
        out = await tools.fobo_evidence_required(s, _ctx(), test_id="FO-6")
        assert set(out["evidence"]) == {"Corporate action file", "Pull factor history"}


async def test_required_on_fail_fo3_needs_fo6():
    async with get_session() as s:
        await _seeded(s)
        out = await tools.fobo_required_on_fail(s, _ctx(), test_id="FO-3")
        assert out["tests"] == ["FO-6"]


async def test_unset_policies_defaults_to_the_workflow_params():
    async with get_session() as s:
        await _seeded(s)
        out = await tools.fobo_unset_policies(s, _ctx())
        assert set(out["params"]) == {"materiality_threshold", "posting_policy_reference"}
        assert set(out["unset"]) <= set(out["params"])
        out = await tools.fobo_unset_policies(s, _ctx(), params=["no_such_policy"])
        assert out["unset"] == ["no_such_policy"]


async def test_book_context_resolves_desk_and_lineage_as_of_business_date():
    async with get_session() as s:
        await _seeded(s)
        out = await tools.fobo_book_context(s, _ctx(), book_ref="PRIME-MB-05")
        assert out["book_id"] == "book:PRIME-MB-05"
        assert out["desk"] == "APAC-CASH"
        assert out["as_of"] == "2026-08-03"
        assert out["lineage"]


async def test_book_context_honours_the_session_business_date():
    async with get_session() as s:
        await _seeded(s)
        ctx = AgentContext("sess-tools", FO, date(2026, 6, 15), {})
        out = await tools.fobo_book_context(s, ctx, book_ref="PRIME-MB-05")
        assert out["desk"] == "APAC-TREASURY"


async def test_caller_outside_scope_cannot_resolve_a_book():
    async with get_session() as s:
        await _seeded(s)
        with pytest.raises(ToolInputError):
            await tools.fobo_book_context(s, _ctx(OUTSIDER), book_ref="PRIME-MB-01")


async def test_unknown_book_is_a_tool_input_error():
    async with get_session() as s:
        await _seeded(s)
        with pytest.raises(ToolInputError):
            await tools.fobo_book_context(s, _ctx(), book_ref="NOPE-01")


async def test_similar_breaks_uses_the_breaks_book_and_line():
    async with get_session() as s:
        await _seeded(s)
        s.add(BreakEvent(
            break_id="OLD-1", book_id="book:PRIME-MB-01", line_code="CASH",
            cob_date=date(2026, 7, 20), pattern_code="P-204", outcome="POST",
            narrative="timing",
        ))
        await s.flush()
        out = await tools.fobo_similar_breaks(s, _ctx(), break_id="B-001")
        old = next(b for b in out["breaks"] if b["break_id"] == "OLD-1")
        assert old["cob_date"] == "2026-07-20"
        assert all(b["book_id"] == "book:PRIME-MB-01" for b in out["breaks"])


async def test_similar_breaks_outside_the_session_is_rejected():
    async with get_session() as s:
        await _seeded(s)
        with pytest.raises(ToolInputError):
            await tools.fobo_similar_breaks(s, _ctx(), break_id="B-999")


async def test_similar_breaks_without_a_resolved_book_is_rejected():
    async with get_session() as s:
        await _seeded(s)
        ctx = _ctx(breaks={"B-001": _brk(1, book_id=None)})
        with pytest.raises(ToolInputError):
            await tools.fobo_similar_breaks(s, ctx, break_id="B-001")


async def test_list_breaks_pages_filters_and_orders():
    breaks = {f"B-{i:03d}": _brk(i, "P-204" if i % 2 else "P-300") for i in range(1, 8)}
    async with get_session() as s:
        ctx = _ctx(breaks=breaks)
        out = await tools.fobo_list_breaks(s, ctx, page=1, page_size=3)
        assert out["total"] == 7 and out["page"] == 1 and out["page_size"] == 3
        assert [b["break_id"] for b in out["breaks"]] == ["B-001", "B-002", "B-003"]
        assert set(out["breaks"][0]) == {
            "break_id", "book", "pattern_code", "break_amount", "line_code"}
        out = await tools.fobo_list_breaks(s, ctx, page=3, page_size=3)
        assert [b["break_id"] for b in out["breaks"]] == ["B-007"]
        out = await tools.fobo_list_breaks(s, ctx, pattern_code="P-300")
        assert out["total"] == 3
        assert all(b["pattern_code"] == "P-300" for b in out["breaks"])


@pytest.mark.parametrize("page,size", [(0, 10), (1, 0), (1, 101)])
async def test_list_breaks_bounds(page, size):
    async with get_session() as s:
        with pytest.raises(ToolInputError):
            await tools.fobo_list_breaks(s, _ctx(), page=page, page_size=size)


async def test_break_detail_and_outside_session():
    async with get_session() as s:
        out = await tools.fobo_break_detail(s, _ctx(), break_id="B-001")
        assert out["break_id"] == "B-001" and out["lineage"] == []
        with pytest.raises(ToolInputError):
            await tools.fobo_break_detail(s, _ctx(), break_id="B-999")


async def test_context_for_token_builds_the_context():
    async with get_session() as s:
        s.add(InvestigationSession(
            investigation_session_id="sess-tools", reconciliation_id="R-1",
            master_book="APAC-CASH", business_date=D, run_id="run-1", status="analysing"))
        await s.flush()
        token, h = sessions.new_token()
        await sessions.create(
            s, investigation_session_id="sess-tools", token_hash=h,
            caller=FO.model_dump(), business_date=D, breaks={"B-001": _brk(1)}, request={})
        await s.commit()
    async with get_session() as s:
        ctx = await context_for_token(s, token)
        assert ctx.caller == FO and ctx.business_date == D
        assert list(ctx.breaks) == ["B-001"]
        assert await context_for_token(s, "wrong") is None


async def _calls(s):
    return (await s.scalars(select(SourceCall))).all()


async def _investigation(s):
    s.add(InvestigationSession(
        investigation_session_id="sess-tools", reconciliation_id="R-1",
        master_book="APAC-CASH", business_date=D, run_id="run-1", status="analysing"))
    await s.flush()


async def test_audited_records_one_agent_source_call():
    async with get_session() as s:
        await _investigation(s)
        ctx = _ctx(breaks={f"B-{i:03d}": _brk(i) for i in range(1, 4)})
        out = await audited(
            s, ctx, "fobo_list_breaks", {"page": 1},
            lambda: tools.fobo_list_breaks(s, ctx, page=1))
        assert out["total"] == 3
        (call,) = await _calls(s)
        assert call.application_name == "agent"
        assert call.tool_name == "fobo_list_breaks"
        assert call.validated_parameters == {"page": 1}
        assert call.row_count == 3
        assert call.error_detail is None
        assert call.latency_ms is not None
        assert len(call.result_rows) == 3


async def test_audited_records_failures_and_reraises():
    async with get_session() as s:
        await _investigation(s)
        ctx = _ctx()
        with pytest.raises(ToolInputError):
            await audited(
                s, ctx, "fobo_break_detail", {"break_id": "B-999"},
                lambda: tools.fobo_break_detail(s, ctx, break_id="B-999"))
        (call,) = await _calls(s)
        assert call.application_name == "agent"
        assert "B-999" in call.error_detail
