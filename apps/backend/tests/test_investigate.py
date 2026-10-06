"""POST /api/recs/{id}/investigate: run a rec's investigation once.

Replaces the classic `GET /api/recs/{id}` (a case dump) and the classic
`/api/sessions/{id}` pair as the way to *start* a run — see spec §5. Reading
the result stays with the console's own `GET /api/recs/{id}` and
`GET /api/recs/{id}/trace`.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from fobo.web.main import create_app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def test_investigating_a_rec_returns_its_session_and_status(client):
    r = await client.post("/api/recs/R-1055/investigate")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "sess-r-1055"
    assert body["status"] == "awaiting_signoff"
    assert body["workflow_version"] == 1


async def test_a_second_post_does_not_re_run_the_investigation(client):
    """Idempotent, like the console's own path to the same investigation:
    the second call reads the existing checkpoint rather than adding to it."""
    first = (await client.post("/api/recs/R-1055/investigate")).json()
    before = (await client.get("/api/recs/R-1055/trace")).json()["trace"]

    second = (await client.post("/api/recs/R-1055/investigate")).json()
    after = (await client.get("/api/recs/R-1055/trace")).json()["trace"]

    assert second["session_id"] == first["session_id"]
    assert after["checkpoints"] == before["checkpoints"]


async def test_concurrent_investigates_of_a_cold_rec_do_not_collide(client):
    """React StrictMode double-fires effects in dev, so the console can issue
    two investigates for the same rec at once against an empty graph."""
    results = await asyncio.gather(
        client.post("/api/recs/R-2031/investigate"),
        client.post("/api/recs/R-2031/investigate"),
        return_exceptions=True,
    )
    for r in results:
        assert not isinstance(r, Exception), r
        assert r.status_code == 200, r.text
    assert results[0].json()["session_id"] == results[1].json()["session_id"]


async def test_an_unknown_rec_is_404(client):
    r = await client.post("/api/recs/R-9999/investigate")
    assert r.status_code == 404


async def test_a_rec_without_breaks_is_409(client):
    r = await client.post("/api/recs/R-1042/investigate")
    assert r.status_code == 409


async def test_the_old_aof_prefixed_board_path_is_gone(client):
    r = await client.get("/api/aof/board")
    assert r.status_code == 404
