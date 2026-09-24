import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=120
    ) as c:
        await c.get("/api/recs/R-1055")
        yield c


async def test_a_book_reports_its_desk_and_entity(client):
    body = (await client.get("/api/books/PRIME-MB-01")).json()
    assert body["book_ref"] == "PRIME-MB-01"
    assert body["desk"] == "APAC-CASH"
    assert body["legal_entity_id"] == "LE-APAC-01"


async def test_a_book_lists_todays_breaks_with_their_reasons(client):
    body = (await client.get("/api/books/PRIME-MB-01")).json()
    assert body["total_breaks"] >= 1
    first = body["breaks"][0]
    assert first["delta"] is not None
    assert first["reason_text"]


async def test_a_book_carrying_two_breaks_shows_both(client):
    """PRIME-MB-09 has two breaks today; the drawer must not collapse them."""
    body = (await client.get("/api/books/PRIME-MB-09")).json()
    assert body["total_breaks"] == 2


async def test_a_book_reports_its_prior_resolutions(client):
    body = (await client.get("/api/books/PRIME-MB-01")).json()
    assert isinstance(body["history"], list)
    for row in body["history"]:
        assert row["outcome"] in {"approved", "rejected"}


async def test_an_unknown_book_is_404(client):
    r = await client.get("/api/books/NOPE-99")
    assert r.status_code == 404


async def test_open_count_excludes_resolved_breaks(client):
    body = (await client.get("/api/books/PRIME-MB-01")).json()
    resolved = [b for b in body["breaks"] if b["outcome"] is not None]
    assert body["open_breaks"] == body["total_breaks"] - len(resolved)
