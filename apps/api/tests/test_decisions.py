import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=120
    ) as c:
        # Opening the case seeds fixtures and runs the investigation.
        await c.get("/api/recs/R-1055")
        yield c


async def _group_id(client, code="P-204"):
    d = (await client.get("/api/recs/R-1055")).json()
    return next(g["group_id"] for g in d["pattern_groups"] if g["pattern_code"] == code)


async def test_approving_a_group_resolves_every_break_in_it(client):
    gid = await _group_id(client)
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "approve", "group_id": gid},
        headers={"Idempotency-Key": "k-approve-1"},
    )
    assert r.status_code == 201
    assert len(r.json()["break_ids"]) == 6


async def test_a_repeated_idempotency_key_is_rejected(client):
    gid = await _group_id(client)
    body = {"action": "approve", "group_id": gid}
    headers = {"Idempotency-Key": "k-dup"}
    first = await client.post("/api/recs/R-1055/decisions", json=body, headers=headers)
    assert first.status_code == 201
    second = await client.post("/api/recs/R-1055/decisions", json=body, headers=headers)
    assert second.status_code == 409


async def test_a_rejection_without_a_reason_is_refused(client):
    """An empty rejection gives the retry cycle nothing to correct."""
    gid = await _group_id(client)
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "reject", "group_id": gid},
        headers={"Idempotency-Key": "k-noreason"},
    )
    assert r.status_code == 422


async def test_a_rejection_with_a_reason_is_accepted(client):
    gid = await _group_id(client)
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "reject", "group_id": gid, "reason": "Amount unverified"},
        headers={"Idempotency-Key": "k-reason"},
    )
    assert r.status_code == 201


async def test_a_single_break_can_be_decided(client):
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "approve", "break_id": "B-1"},
        headers={"Idempotency-Key": "k-one"},
    )
    assert r.status_code == 201
    assert r.json()["break_ids"] == ["B-1"]


async def test_an_unknown_group_is_404(client):
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "approve", "group_id": "nope"},
        headers={"Idempotency-Key": "k-unknown"},
    )
    assert r.status_code == 404


async def test_a_decision_with_neither_group_nor_break_is_refused(client):
    r = await client.post(
        "/api/recs/R-1055/decisions",
        json={"action": "approve"},
        headers={"Idempotency-Key": "k-empty"},
    )
    assert r.status_code == 422


async def test_the_missing_idempotency_header_is_refused(client):
    gid = await _group_id(client)
    r = await client.post(
        "/api/recs/R-1055/decisions", json={"action": "approve", "group_id": gid}
    )
    assert r.status_code == 422
