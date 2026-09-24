"""Asking a Helix session a question, and deciding adjustments from it."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from api.main import create_app
from app.db.base import get_session
from app.db.models_session import SessionMessage


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def _ask(client, rec_id: str, message: str):
    return await client.post(f"/api/helix/recs/{rec_id}/messages", json={"message": message})


async def _decide(client, key: str, body: dict, rec_id: str = "R-1055"):
    return await client.post(f"/api/helix/recs/{rec_id}/decisions", json=body,
                             headers={"Idempotency-Key": key})


async def test_naming_an_adjustment_explains_it_and_records_the_lookup(client):
    r = await _ask(client, "R-1055", "Why is B-9 flagged as ungrounded?")
    assert r.status_code == 201
    agent = r.json()["agent"]
    assert agent["answeredBy"] == "router:adjustment"
    assert agent["blocks"][0]["text"].startswith("B-9 on PRIME-MB-11")
    assert any(b["type"] == "risk" for b in agent["blocks"])
    tools = [f"{c['server']}.{c['tool']}" for c in agent["calls"]]
    assert tools == ["mbrec.get_break_legs", "helix.grounding_check"]


async def test_the_conversation_survives_a_reload(client):
    await _ask(client, "R-1055", "What is safe to approve?")
    prime = (await client.get("/api/helix/recs/R-1055")).json()
    roles = [m["role"] for m in prime["session"]]
    assert roles == ["agent", "user", "agent"]
    assert prime["session"][1]["text"] == "What is safe to approve?"


async def test_an_answers_calls_stay_out_of_the_analysis_turn(client):
    before = len((await client.get("/api/helix/recs/R-1055")).json()["calls"])
    await _ask(client, "R-1055", "Explain B-1")
    after = (await client.get("/api/helix/recs/R-1055")).json()
    assert len(after["calls"]) == before
    assert after["session"][-1]["calls"]


async def test_safe_to_approve_separates_what_posts_from_what_waits(client):
    blocks = (await _ask(client, "R-1055", "What is safe to approve?")).json()["agent"]["blocks"]
    by_title = {b["title"]: b["items"] for b in blocks if b["type"] == "list"}
    assert by_title["Grounded, single cause, fix proposed"] == ["P-204 FX timing lag: 6 books, USD 15,965"]
    held = " ".join(by_title["Hold, no posting proposed yet"])
    assert "CPTY-REF" in held and "LATE-BOOK" in held and "ungrounded" in held


async def test_an_unrecognised_question_is_not_guessed_at(client):
    agent = (await _ask(client, "R-1055", "what is the weather in london")).json()["agent"]
    assert agent["answeredBy"] == "router:unmatched"
    assert "reasoner: none" in agent["blocks"][-1]["text"]
    assert agent["calls"] == []


async def test_a_rec_with_no_session_cannot_be_asked(client):
    r = await _ask(client, "R-3019", "hello")
    assert r.status_code == 409


async def test_an_empty_question_is_rejected(client):
    assert (await _ask(client, "R-1055", "   ")).status_code == 422


async def test_approving_updates_the_rec_the_session_and_the_feed(client):
    await client.get("/api/helix/board")
    r = await _decide(client, "k-approve",
                      {"ids": ["B-1", "B-2", "B-3", "B-4", "B-5", "B-6"], "decision": "Approved"})
    assert r.status_code == 201
    body = r.json()
    status = {a["id"]: a["status"] for a in body["rec"]["adjustments"]}
    assert all(status[f"B-{i}"] == "Approved" for i in range(1, 7))
    assert status["B-7"] == "Pending"
    note = body["rec"]["session"][-1]
    assert note["role"] == "system" and note["tone"] == "approved"
    assert "approved 6 adjustments" in note["text"] and "USD 15,965" in note["text"]
    assert body["activity"][0]["text"] == "Approved: 6 adj on Prime (USD 15,965)"


async def test_rejecting_needs_a_reason(client):
    await client.get("/api/helix/board")
    r = await _decide(client, "k-reject", {"ids": ["B-7"], "decision": "Rejected"})
    assert r.status_code == 422


async def test_a_decided_adjustment_cannot_be_decided_again(client):
    await client.get("/api/helix/board")
    assert (await _decide(client, "k-1", {"ids": ["B-1"], "decision": "Approved"})).status_code == 201
    assert (await _decide(client, "k-2", {"ids": ["B-1"], "decision": "Approved"})).status_code == 409


async def test_a_repeated_idempotency_key_records_nothing_twice(client):
    await client.get("/api/helix/board")
    assert (await _decide(client, "k-same", {"ids": ["B-2"], "decision": "Approved"})).status_code == 201
    assert (await _decide(client, "k-same", {"ids": ["B-3"], "decision": "Approved"})).status_code == 409
    rec = (await client.get("/api/helix/recs/R-1055")).json()
    assert {a["id"]: a["status"] for a in rec["adjustments"]}["B-3"] == "Pending"


async def test_asking_stores_both_turns(client):
    await _ask(client, "R-1055", "Summarise what's pending")
    async with get_session() as s:
        n = await s.scalar(select(func.count()).select_from(SessionMessage))
    assert n == 2
