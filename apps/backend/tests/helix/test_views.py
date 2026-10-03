"""The unified views never show more than the per-case reads would."""

from tests.helix.conftest import RECON, VARIANCE


async def _open(api, user, capability, key):
    res = await api.post(f"/api/capabilities/{capability}/cases", json={"case_key": key},
                         headers=api.as_user(user))
    assert res.status_code == 201, res.text
    return res.json()


async def test_inbox_lists_what_waits_on_me_across_capabilities(api):
    uk = await _open(api, "bob", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    us = await _open(api, "bob", VARIANCE, {"entity": "US01", "period": "2026-09"})
    cash = await _open(api, "dan", RECON, {"entity": "UK01", "date": "2026-10-02"})

    alice = (await api.get("/api/inbox", headers=api.as_user("alice"))).json()
    assert [r["case_id"] for r in alice] == [uk["case_id"]]          # UK01 only, finance only
    assert alice[0]["action"] == "review" and alice[0]["case_label"] == "Lane"

    bob = {r["case_id"] for r in (await api.get("/api/inbox", headers=api.as_user("bob"))).json()}
    assert bob == {uk["case_id"], us["case_id"]}
    dan = {r["case_id"] for r in (await api.get("/api/inbox", headers=api.as_user("dan"))).json()}
    assert dan == {cash["case_id"]}
    assert (await api.get("/api/inbox", headers=api.as_user("viewer"))).json() == []


async def test_inbox_moves_a_case_from_review_to_release_for_someone_else(api):
    case = await _open(api, "alice", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"inbox-{g['group_id']}"})
    assert (await api.get("/api/inbox", headers=api.as_user("alice"))).json() == []
    bob = (await api.get("/api/inbox", headers=api.as_user("bob"))).json()
    assert [(r["case_id"], r["action"]) for r in bob] == [(case["case_id"], "release")]


async def test_overview_and_audit_are_scoped(api):
    await _open(api, "bob", VARIANCE, {"entity": "US01", "period": "2026-09"})
    await _open(api, "alice", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    alice = (await api.get("/api/overview", headers=api.as_user("alice"))).json()
    assert alice["awaiting_my_review"] == 1 and alice["open_cases"] == 1
    assert [c["id"] for c in alice["capabilities"]] == [VARIANCE]
    assert alice["tool_calls_24h"] > 0

    events = (await api.get("/api/audit", headers=api.as_user("alice"))).json()
    assert events and all("UK01" in e["subject"] for e in events)
    assert {e["kind"] for e in events} == {"tool_call"}
