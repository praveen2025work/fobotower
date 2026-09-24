"""The Helix board: every rec as the console renders it, from real rows."""

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def _board(client) -> dict:
    r = await client.get("/api/helix/board")
    assert r.status_code == 200
    return r.json()


def _rec(board: dict, rec_id: str) -> dict:
    return next(r for r in board["recs"] if r["id"] == rec_id)


async def test_the_board_lists_the_seven_recs_in_window_order(client):
    board = await _board(client)
    assert [r["id"] for r in board["recs"]] == [
        "R-1042", "R-1055", "R-2031", "R-2048", "R-3019", "R-3026", "R-1061",
    ]
    assert {r["id"]: r["status"] for r in board["recs"]} == {
        "R-1042": "Cleared",
        "R-1055": "Awaiting Sign-off",
        "R-2031": "In Progress",
        "R-2048": "Blocked",
        "R-3019": "Awaiting Ready",
        "R-3026": "Cleared",
        "R-1061": "Awaiting Ready",
    }


async def test_steps_follow_the_run_status(client):
    board = await _board(client)
    assert _rec(board, "R-1055")["steps"] == ["done", "done", "done", "active", "pending"]
    assert _rec(board, "R-2048")["steps"] == ["done", "done", "blocked", "pending", "pending"]
    assert _rec(board, "R-3019")["steps"][0] == "active"


async def test_a_rec_waiting_for_its_ready_event_has_no_session(client):
    fx = _rec(await _board(client), "R-1061")
    assert fx["readyAt"] is None and fx["eventId"] is None
    assert fx["mb"] == {"available": 6, "total": 15}
    assert fx["analysis"] is None
    assert fx["session"] == [] and fx["sessionId"] is None


async def test_prime_adjustments_come_from_the_investigation(client):
    prime = _rec(await _board(client), "R-1055")
    adjs = {a["id"]: a for a in prime["adjustments"]}
    assert len(adjs) == 14
    assert adjs["B-1"]["amount"] == "$2,340"
    assert adjs["B-1"]["book"] == "PRIME-MB-01"
    assert adjs["B-1"]["type"] == "Auto" and adjs["B-7"]["type"] == "Manual"
    assert all(a["status"] == "Pending" for a in adjs.values())


async def test_the_ungrounded_figure_is_flagged_and_named_in_the_risk(client):
    prime = _rec(await _board(client), "R-1055")
    ungrounded = [a["id"] for a in prime["adjustments"] if not a["grounded"]]
    assert ungrounded == ["B-9"]
    assert prime["analysis"]["risk"].startswith("B-9 has an ungrounded figure")
    assert prime["analysis"]["confidence"] == "MEDIUM"


async def test_carried_breaks_report_how_many_sessions_they_aged(client):
    prime = _rec(await _board(client), "R-1055")
    aged = {a["id"]: a["agedSessions"] for a in prime["adjustments"]}
    assert (aged["B-12"], aged["B-13"], aged["B-14"]) == (3, 3, 2)
    assert aged["B-1"] == 0


async def test_a_fix_is_proposed_only_where_the_playbook_posts(client):
    prime = _rec(await _board(client), "R-1055")
    adjs = {a["id"]: a for a in prime["adjustments"]}
    assert adjs["B-1"]["detail"]["verdict"] == "POST" and adjs["B-1"]["detail"]["fix"]
    # An FO-side late booking never posts (R2); nor does a data quality break.
    assert adjs["B-12"]["detail"]["fix"] is None
    assert adjs["B-7"]["detail"]["fix"] is None
    assert "Technology" in " ".join(adjs["B-7"]["detail"]["verify"])


async def test_break_detail_shows_both_legs_as_mb_rec_reports_them(client):
    prime = _rec(await _board(client), "R-1055")
    b1 = next(a for a in prime["adjustments"] if a["id"] == "B-1")
    assert b1["detail"]["cats"]["value"] == "USD 102,340.00"
    assert b1["detail"]["motif"]["value"] == "USD 100,000.00"
    assert b1["detail"]["gap"]["value"] == "USD 2,340.00"
    assert [leg["amount"] for leg in b1["legs"]["cats"]] == [102340.0]


async def test_the_blocked_rec_drafts_nothing_and_says_who_can_fix_it(client):
    coll = _rec(await _board(client), "R-2048")
    assert coll["adjustments"] == []
    assert coll["blockedBreak"] == {"id": "COLL-7781", "book": "COLL-MB-03", "amount": 214500.0}
    assert coll["analysis"]["confidence"] == "BLOCKED"
    assert "4 consecutive sessions" in coll["analysis"]["why"]


async def test_a_running_rec_shows_a_running_analysis(client):
    fi = _rec(await _board(client), "R-2031")
    assert fi["analysis"]["confidence"] == "RUNNING"
    assert fi["adjustments"] == []


async def test_a_cleared_rec_shows_what_it_resolved(client):
    rates = _rec(await _board(client), "R-1042")
    assert [(a["id"], a["status"], a["type"]) for a in rates["adjustments"]] == [
        ("A-1", "Posted", "Auto"), ("A-2", "Posted", "Auto"), ("A-3", "Approved", "Manual"),
    ]
    assert rates["booksUnlocked"] == 34
    assert "all 34 books are unlocked" in rates["analysis"]["action"]


async def test_the_analysis_turn_carries_the_investigations_calls(client):
    prime = _rec(await _board(client), "R-1055")
    tools = [f"{c['server']}.{c['tool']}" for c in prime["calls"]]
    assert tools == [
        "mbrec.get_breaks", "mbrec.get_break_legs", "helix.kg_lineage",
        "helix.similar_breaks", "helix.grounding_check",
    ]
    grounding = prime["calls"][-1]
    assert grounding["summary"] == "1 not traced"
    assert {r["adjId"]: r["result"] for r in grounding["rows"]}["B-9"] == "Not traced"
    assert prime["session"][0]["kind"] == "analysis"


async def test_a_cleared_session_reads_back_its_breaks_once(client):
    await _board(client)
    rates = _rec(await _board(client), "R-1042")
    assert [f"{c['server']}.{c['tool']}" for c in rates["calls"]] == [
        "mbrec.get_breaks", "helix.grounding_check",
    ]


async def test_the_feed_is_derived_from_the_runs(client):
    feed = (await _board(client))["activity"]
    texts = [e["text"] for e in feed]
    assert "Ready event EVT-RDY-80437 received: Prime session started" in texts
    assert "MB Rec readiness (One Fin UX): FX 6/15 master books ready" in texts
    assert "Book Unlocked: 19 books via Master Book ↔ P&L Mapping" in texts
    assert "Awaiting sign-off: Prime, 14 adjustments across 4 patterns" in texts
    assert feed[0]["time"] == "17:36"
