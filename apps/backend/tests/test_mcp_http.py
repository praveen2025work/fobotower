"""The MCP server over HTTP: mounted at /mcp only when FOBO_MCP_URL is set,
and answering only a live agent session's bearer token.

Raw JSON-RPC, so the test pins the wire behaviour the harness relies on, not
an SDK client's interpretation of it.
"""

from datetime import date

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fobo.contracts.models import Caller
from fobo.db.base import get_session
from fobo.db.models_ops import SourceCall
from fobo.db.models_session import InvestigationSession
from fobo.playbook.loader import load_playbook
from fobo.reasoning import agent_sessions as sessions
from fobo.web.main import create_app
from seed_data.loader import load_all

D = date(2026, 8, 3)
SESSION_ID = "sess-mcp-http"
FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
BASE_URL = "http://localhost:8000"
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
TOOL_NAMES = {
    "fobo_list_tests", "fobo_evidence_required", "fobo_required_on_fail",
    "fobo_unset_policies", "fobo_book_context", "fobo_similar_breaks",
    "fobo_list_breaks", "fobo_break_detail",
}
UNAUTHORISED = {"error": "invalid or expired agent session token"}


def _brk(i: int) -> dict:
    return {
        "break_id": f"B-{i:03d}", "book": "PRIME-MB-01", "line_code": "CASH",
        "cob_date": "2026-08-03", "fo_value": 1.0, "bo_value": 2.0, "break_amount": -1.0,
        "checks": [], "prior_resolutions": [], "lineage": [],
        "pattern_code": "P-204", "book_id": "book:PRIME-MB-01",
    }


async def _agent_session(status: str = "running") -> str:
    """Seed the graph and one agent session in the given status; its token."""
    async with get_session() as s:
        await load_all(s)
        await load_playbook(s)
        s.add(InvestigationSession(
            investigation_session_id=SESSION_ID, reconciliation_id="R-1",
            master_book="APAC-CASH", business_date=D, run_id="run-1", status="analysing"))
        await s.flush()
        token, h = sessions.new_token()
        row = await sessions.create(
            s, investigation_session_id=SESSION_ID, token_hash=h,
            caller=FO.model_dump(), business_date=D, breaks={"B-001": _brk(1)}, request={})
        if status == "running":
            await sessions.mark_running(s, row, "harness-1")
        elif status == "completed":
            await sessions.mark_completed(s, row, {})
        await s.commit()
    return token


@asynccontextmanager
async def _mcp_client(monkeypatch):
    """A client for an app built with FOBO_MCP_URL set.

    ASGITransport never runs the lifespan, and the MCP session manager must be
    running, so the app's own lifespan wraps the client. A context manager in
    the test rather than a fixture: the session manager's task group must be
    entered and exited in the same task.
    """
    monkeypatch.setenv("FOBO_MCP_URL", f"{BASE_URL}/mcp")
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as c:
            yield c


def _rpc(method: str, params: dict | None = None, rid: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    return body


async def _post(client, body: dict, token: str | None):
    headers = dict(HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return await client.post("/mcp", json=body, headers=headers)


async def _call(client, token: str, name: str, arguments: dict) -> dict:
    r = await _post(client, _rpc("tools/call", {"name": name, "arguments": arguments}), token)
    assert r.status_code == 200, r.text
    return r.json()["result"]


async def test_no_mcp_url_means_no_mcp_route(monkeypatch):
    monkeypatch.delenv("FOBO_MCP_URL", raising=False)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as c:
        r = await c.post("/mcp", json=_rpc("tools/list"), headers=HEADERS)
    assert r.status_code == 404


async def test_no_token_is_401(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        r = await _post(client, _rpc("tools/list"), None)
        assert r.status_code == 401
        assert r.json() == UNAUTHORISED


async def test_unknown_token_is_401(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        await _agent_session()
        r = await _post(client, _rpc("tools/list"), "not-a-session-token")
        assert r.status_code == 401
        assert r.json() == UNAUTHORISED


async def test_token_of_a_completed_session_is_401(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session(status="completed")
        r = await _post(client, _rpc("tools/list"), token)
        assert r.status_code == 401
        assert r.json() == UNAUTHORISED


async def test_valid_token_lists_exactly_the_eight_tools(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session()
        r = await _post(client, _rpc("tools/list"), token)
        assert r.status_code == 200, r.text
        tools = r.json()["result"]["tools"]
        assert {t["name"] for t in tools} == TOOL_NAMES
        assert all(t["description"] for t in tools)
        detail = next(t for t in tools if t["name"] == "fobo_break_detail")
        assert detail["inputSchema"]["required"] == ["break_id"]


async def test_a_starting_session_token_is_accepted(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session(status="starting")
        r = await _post(client, _rpc("tools/list"), token)
        assert r.status_code == 200, r.text


async def test_evidence_required_answers_and_writes_one_agent_source_call(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session()
        result = await _call(client, token, "fobo_evidence_required", {"test_id": "FO-6"})
        assert not result.get("isError")
        payload = result["structuredContent"]
        assert set(payload["evidence"]) == {"Corporate action file", "Pull factor history"}
        async with get_session() as s:
            rows = (await s.execute(select(SourceCall).where(
                SourceCall.investigation_session_id == SESSION_ID))).scalars().all()
        assert len(rows) == 1
        assert rows[0].application_name == "agent"
        assert rows[0].row_count == 2


async def test_break_outside_the_session_is_a_tool_error_not_data(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session()
        result = await _call(client, token, "fobo_break_detail", {"break_id": "B-999"})
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "B-999" in text and "not one of this session's breaks" in text
        assert "Traceback" not in text
        assert "structuredContent" not in result or not result["structuredContent"]
        async with get_session() as s:
            row = (await s.execute(select(SourceCall).where(
                SourceCall.investigation_session_id == SESSION_ID))).scalar_one()
        assert row.tool_name == "fobo_break_detail" and row.error_detail


async def test_list_breaks_returns_the_session_breaks(monkeypatch):
    async with _mcp_client(monkeypatch) as client:
        token = await _agent_session()
        result = await _call(client, token, "fobo_list_breaks", {"page_size": 10})
        assert not result.get("isError")
        assert result["structuredContent"]["total"] == 1
        assert result["structuredContent"]["breaks"][0]["break_id"] == "B-001"


@pytest.mark.parametrize("bad", ["orch/mcp", "ftp://orch/mcp", "/mcp", "https:///mcp"])
def test_a_malformed_mcp_url_fails_at_app_build(monkeypatch, bad):
    monkeypatch.setenv("FOBO_MCP_URL", bad)
    with pytest.raises(ValueError, match="FOBO_MCP_URL.*https://host/mcp"):
        create_app()
