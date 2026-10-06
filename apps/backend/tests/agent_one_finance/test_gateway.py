import pytest
from sqlalchemy import select

from agent_one_finance import gateway
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.models import ToolCall

UK = Caller("alice", frozenset({"FIN_PREPARER"}), {"entity": frozenset({"UK01"})})


def _ctx(tools=("gl.balances",), caller=UK):
    return gateway.CallContext(capability_id="fin.variance-commentary", caller=caller,
                               allowed_tools=frozenset(tools), case_id=None)


async def _rows():
    async with get_session() as s:
        return (await s.execute(select(ToolCall).order_by(ToolCall.called_at))).scalars().all()


async def test_an_allowed_call_reaches_the_connector_and_is_recorded():
    result = await gateway.call(_ctx(), "gl.balances", {"entity": "UK01", "period": "2026-09"})
    assert len(result["rows"]) == 14
    [row] = await _rows()
    assert (row.allowed, row.tool, row.connector_id, row.row_count, row.caller) == \
        (True, "gl.balances", "gl", 14, "alice")
    assert row.result == result


async def test_a_tool_the_capability_was_not_given_is_refused_and_recorded():
    with pytest.raises(gateway.ToolDenied, match="not allowed for capability"):
        await gateway.call(_ctx(tools=()), "gl.balances", {"entity": "UK01", "period": "2026-09"})
    [row] = await _rows()
    assert row.allowed is False and row.result is None


async def test_data_outside_the_callers_scope_is_refused_before_the_connector_is_called():
    with pytest.raises(gateway.ToolDenied, match="not entitled to entity=US01"):
        await gateway.call(_ctx(), "gl.balances", {"entity": "US01", "period": "2026-09"})
    [row] = await _rows()
    assert row.allowed is False and "US01" in row.denied_reason


async def test_a_scoped_tool_without_its_scope_argument_is_refused():
    with pytest.raises(gateway.ToolDenied, match="needs `entity`"):
        await gateway.call(_ctx(), "gl.balances", {"period": "2026-09"})


async def test_an_unknown_tool_is_refused():
    with pytest.raises(gateway.ToolDenied, match="not an onboarded connector tool"):
        await gateway.call(_ctx(tools=("gl.drop_tables",)), "gl.drop_tables", {})


async def test_a_connector_error_is_recorded_and_raised():
    with pytest.raises(gateway.ToolFailed):
        await gateway.call(_ctx(), "gl.balances", {"entity": "UK01"})  # period missing
    [row] = await _rows()
    assert row.allowed is True and row.error
