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


async def test_session_maps_breaks_to_their_books(client):
    """Adjustment rows show the book a controller recognises, not b-01."""
    await client.post("/api/sessions/sess-books/investigate")
    body = (await client.get("/api/sessions/sess-books")).json()
    assert body["break_books"]["b-01"] == "APAC-CASH-01"
    assert len(body["break_books"]) == 14


async def test_concurrent_investigates_from_an_empty_graph(client):
    """React StrictMode double-fires effects in dev, so the console issues
    two investigates at once against a cold graph. A check-then-act seed
    lets both see it empty and both insert, and one 500s.

    The graph must be empty for this to reproduce — the client fixture
    seeds, so truncate first.
    """
    import asyncio

    from sqlalchemy import text

    from tests.conftest import TABLES

    async with get_session() as s:
        await s.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        await s.commit()

    results = await asyncio.gather(
        client.post("/api/sessions/sess-cold-a/investigate"),
        client.post("/api/sessions/sess-cold-b/investigate"),
        return_exceptions=True,
    )
    for r in results:
        assert not isinstance(r, Exception), r
        assert r.status_code == 202, r.text


async def test_concurrent_investigates_do_not_collide(client):
    """React StrictMode double-fires effects in dev, so the console issues
    two investigates at once. Both must succeed: a check-then-act seed
    lets both see an empty graph and both insert."""
    import asyncio

    results = await asyncio.gather(
        client.post("/api/sessions/sess-race/investigate"),
        client.post("/api/sessions/sess-race/investigate"),
        return_exceptions=True,
    )
    for r in results:
        assert not isinstance(r, Exception), r
        assert r.status_code == 202, r.text

    body = (await client.get("/api/sessions/sess-race")).json()
    assert len(body["pattern_groups"]) == 4


async def test_investigate_is_idempotent(client):
    """Calling it twice sequentially leaves one coherent session, not two."""
    await client.post("/api/sessions/sess-idem/investigate")
    first = (await client.get("/api/sessions/sess-idem")).json()
    await client.post("/api/sessions/sess-idem/investigate")
    second = (await client.get("/api/sessions/sess-idem")).json()
    assert first["pattern_groups"] == second["pattern_groups"]
    assert second["session"]["status"] == "awaiting_signoff"


async def test_two_investigates_on_the_same_thread_from_a_cold_graph(client):
    """The exact browser scenario: StrictMode fires the same effect twice,
    so both calls target one session id against an empty graph."""
    import asyncio

    from sqlalchemy import text

    from tests.conftest import TABLES

    async with get_session() as s:
        await s.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        await s.commit()

    results = await asyncio.gather(
        client.post("/api/sessions/sess-same/investigate"),
        client.post("/api/sessions/sess-same/investigate"),
        return_exceptions=True,
    )
    for r in results:
        assert not isinstance(r, Exception), r
        assert r.status_code == 202, r.text

    body = (await client.get("/api/sessions/sess-same")).json()
    assert len(body["pattern_groups"]) == 4
    assert body["session"]["status"] == "awaiting_signoff"
    assert len(body["break_books"]) == 14
