import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def _trace(client, rec):
    return (await client.get(f"/api/recs/{rec}/trace")).json()


async def test_the_trace_lists_every_workflow_step_in_order(client):
    await client.get("/api/recs/R-1055")
    trace = (await _trace(client, "R-1055"))["trace"]
    assert [s["node"] for s in trace["steps"]] == [
        "resolve", "gather", "group", "reason", "rank",
        "draft", "validate", "review", "record",
    ]


async def test_steps_before_the_interrupt_are_done_and_review_is_waiting(client):
    await client.get("/api/recs/R-1055")
    trace = (await _trace(client, "R-1055"))["trace"]
    status = {s["node"]: s["status"] for s in trace["steps"]}
    assert all(status[n] == "done" for n in ("resolve", "gather", "group", "reason"))
    assert status["review"] == "waiting"
    assert status["record"] == "pending"
    assert trace["status"] == "awaiting_signoff"


async def test_done_steps_carry_their_recorded_timing(client):
    """Timing comes from the checkpoints — it is recorded, not estimated."""
    await client.get("/api/recs/R-1055")
    trace = (await _trace(client, "R-1055"))["trace"]
    for step in trace["steps"]:
        if step["status"] == "done":
            assert step["duration_ms"] is not None and step["duration_ms"] >= 0


async def test_the_playbook_step_reports_the_deterministic_split(client):
    await client.get("/api/recs/R-2031")
    trace = (await _trace(client, "R-2031"))["trace"]
    reason = next(s for s in trace["steps"] if s["node"] == "reason")
    assert reason["summary"] == "3 of 8 settled by playbook · 5 need judgement"


async def test_steps_report_what_they_added_to_the_state(client):
    await client.get("/api/recs/R-1055")
    trace = (await _trace(client, "R-1055"))["trace"]
    reason = next(s for s in trace["steps"] if s["node"] == "reason")
    assert "findings" in reason["produced"]
    assert "determinism" in reason["produced"]


async def test_a_clear_rec_has_no_trace(client):
    body = await _trace(client, "R-1042")
    assert body["state"] == "clear"
    assert body["trace"] is None
