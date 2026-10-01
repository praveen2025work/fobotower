"""The stub harness speaks contract v2 and reads breaks through the real MCP server.

It is a demo double, but the demo is only honest if the stub calls the same
/mcp the real harness will, with the same token, and answers in a shape the
orchestrator accepts.
"""

import asyncio

import httpx2
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fobo.db.base import get_session
from fobo.db.models_ops import SourceCall
from fobo.reasoning.contracts import RecVerdict
from fobo.web.main import create_app
from scripts import stub_harness
from tests.test_mcp_http import BASE_URL, SESSION_ID, _agent_session

PATTERNS = [{"pattern_code": "P-204", "label": "Cash", "break_count": 1,
             "total_amount": 1.0, "sample": [{"break_id": "B-001"}]}]


def _request(mcp: dict | None = None) -> dict:
    request = {"skill_id": "fobo-investigation", "correlation_id": "sess-x",
               "inputs": {"rec": {}, "patterns": PATTERNS, "already_established": {}}}
    if mcp:
        request["mcp"] = mcp
    return request


async def _until_done(client: AsyncClient, session_id: str) -> dict:
    for _ in range(100):
        payload = (await client.get(f"/sessions/{session_id}")).json()
        if payload["status"] != "running":
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError("stub session never finished")


async def test_start_then_poll_completes_with_a_valid_rec_verdict():
    transport = ASGITransport(app=stub_harness.app)
    async with AsyncClient(transport=transport, base_url="http://stub") as client:
        started = (await client.post("/sessions", json=_request())).json()
        assert started["status"] == "running"
        assert started["correlation_id"] == "sess-x"
        assert started["session_id"].startswith("stub-")
        done = await _until_done(client, started["session_id"])
    assert done["status"] == "completed"
    verdict = RecVerdict.model_validate(done["output"])
    pattern = verdict.patterns[0]
    assert (pattern.pattern_code, pattern.verdict, pattern.root_cause.side) == ("P-204", "POST", "BO")
    assert pattern.classification.category_code == "G"
    assert pattern.requires_sme_review is True
    assert len(pattern.checks_performed) == 1
    assert "read 1 break" in verdict.summary
    assert (done["tool_calls"], done["usage"], done["total_cost_usd"]) == ([], {}, 0)


async def test_an_unknown_session_is_404():
    transport = ASGITransport(app=stub_harness.app)
    async with AsyncClient(transport=transport, base_url="http://stub") as client:
        assert (await client.get("/sessions/stub-nope")).status_code == 404


async def test_it_reads_the_breaks_through_the_orchestrators_mcp(monkeypatch):
    token = await _agent_session()
    monkeypatch.setenv("FOBO_MCP_URL", f"{BASE_URL}/mcp")
    backend = create_app()
    async with backend.router.lifespan_context(backend):
        http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=backend),
                                  headers={"Authorization": f"Bearer {token}"})
        async with http:
            done = await stub_harness.run_session(
                "stub-mcp", _request({"url": f"{BASE_URL}/mcp", "token": token}),
                http_client=http)
    assert done["status"] == "completed", done.get("error")
    assert [c["tool"] for c in done["tool_calls"]] == [
        "mcp__fobo__fobo_list_breaks", "mcp__fobo__fobo_break_detail"]
    assert done["tool_calls"][1]["arguments"] == {"break_id": "B-001"}
    async with get_session() as s:
        audited = (await s.scalars(select(SourceCall.tool_name).where(
            SourceCall.investigation_session_id == SESSION_ID,
            SourceCall.application_name == "agent"))).all()
    assert sorted(audited) == ["fobo_break_detail", "fobo_list_breaks"]


async def test_a_rejected_token_fails_the_session(monkeypatch):
    await _agent_session()
    monkeypatch.setenv("FOBO_MCP_URL", f"{BASE_URL}/mcp")
    backend = create_app()
    async with backend.router.lifespan_context(backend):
        http = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=backend),
                                  headers={"Authorization": "Bearer wrong"})
        async with http:
            done = await stub_harness.run_session(
                "stub-bad", _request({"url": f"{BASE_URL}/mcp", "token": "wrong"}),
                http_client=http)
    assert done["status"] == "failed"
    assert done["error"]["code"] == "stub_error"
    assert "output" not in done
