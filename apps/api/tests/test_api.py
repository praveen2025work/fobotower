import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from app.db.base import get_session
from fixtures.loader import load_all


@pytest.fixture
async def client():
    async with get_session() as s:
        await load_all(s)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_runs_returns_three_regions(client):
    r = await client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert {x["region"] for x in body["regions"]} == {"APAC", "EMEA", "AMER"}


async def test_runs_carries_the_stat_chips_the_header_shows(client):
    body = (await client.get("/api/runs")).json()
    for key in (
        "recs",
        "cleared",
        "awaiting",
        "blocked",
        "adj_pending",
        "auto_posted",
        "books_open",
        "books_not_open",
    ):
        assert key in body["stats"], f"missing stat: {key}"


async def test_run_windows_match_the_mock(client):
    body = (await client.get("/api/runs")).json()
    assert body["run_windows"] == ["11:00", "15:00", "17:00", "19:00"]


async def test_investigate_then_read_the_session(client):
    r = await client.post("/api/sessions/sess-api/investigate")
    assert r.status_code == 202
    body = (await client.get("/api/sessions/sess-api")).json()
    assert len(body["pattern_groups"]) == 4
    assert body["draft"]["what_happened"]


async def test_a_parked_session_reports_awaiting_signoff(client):
    await client.post("/api/sessions/sess-parked/investigate")
    body = (await client.get("/api/sessions/sess-parked")).json()
    assert body["session"]["status"] == "awaiting_signoff"
    assert body["pipeline_stage"] == "signoff"


async def test_pipeline_stages_are_served_not_hardcoded_in_the_client(client):
    await client.post("/api/sessions/sess-stages/investigate")
    body = (await client.get("/api/sessions/sess-stages")).json()
    keys = [s["key"] for s in body["pipeline_stages"]]
    assert keys == ["mbr", "analysis", "signoff", "post", "notify"]


async def test_unknown_session_is_404_not_an_empty_shell(client):
    r = await client.get("/api/sessions/does-not-exist")
    assert r.status_code == 404


async def test_breaks_are_paged(client):
    await client.post("/api/sessions/sess-breaks/investigate")
    body = (await client.get("/api/breaks?session_id=sess-breaks&limit=5")).json()
    assert len(body["breaks"]) == 5
    assert body["total"] == 14
    assert body["truncated"] is True


async def test_the_last_page_is_not_marked_truncated(client):
    await client.post("/api/sessions/sess-last/investigate")
    body = (
        await client.get("/api/breaks?session_id=sess-last&limit=5&offset=10")
    ).json()
    assert len(body["breaks"]) == 4
    assert body["truncated"] is False


async def test_breaks_carry_their_delta(client):
    await client.post("/api/sessions/sess-delta/investigate")
    body = (await client.get("/api/breaks?session_id=sess-delta")).json()
    first = next(b for b in body["breaks"] if b["break_id"] == "b-01")
    assert first["delta"] == pytest.approx(2340.0)
