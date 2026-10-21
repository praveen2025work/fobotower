"""The unified views never show more than the per-task reads would."""

from tests.agent_one_finance.conftest import CASH, RECON, VARIANCE


async def _open(api, user, agent, key, group=None):
    res = await api.post(f"/api/agents/{agent}/tasks",
                         json={"task_key": key, "team_group": group}, headers=api.as_user(user))
    assert res.status_code == 201, res.text
    return res.json()


async def test_inbox_lists_what_waits_on_me_across_agents(api):
    uk = await _open(api, "bob", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    us = await _open(api, "bob", VARIANCE, {"entity": "US01", "period": "2026-09"})
    cash = await _open(api, "dan", RECON, {"entity": "UK01", "date": "2026-10-02"}, CASH)

    alice = (await api.get("/api/inbox", headers=api.as_user("alice"))).json()
    assert [r["task_id"] for r in alice] == [uk["task_id"]]          # UK01 only, finance only
    assert alice[0]["action"] == "review" and alice[0]["task_label"] == "Lane"

    bob = {r["task_id"] for r in (await api.get("/api/inbox", headers=api.as_user("bob"))).json()}
    assert bob == {uk["task_id"], us["task_id"]}
    dan = {r["task_id"] for r in (await api.get("/api/inbox", headers=api.as_user("dan"))).json()}
    assert dan == {cash["task_id"]}
    assert (await api.get("/api/inbox", headers=api.as_user("viewer"))).json() == []


async def test_inbox_moves_a_task_from_review_to_release_for_someone_else(api):
    task = await _open(api, "alice", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    for g in task["groups"]:
        await api.post(f"/api/tasks/{task['task_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"inbox-{g['group_id']}"})
    assert (await api.get("/api/inbox", headers=api.as_user("alice"))).json() == []
    bob = (await api.get("/api/inbox", headers=api.as_user("bob"))).json()
    assert [(r["task_id"], r["action"]) for r in bob] == [(task["task_id"], "release")]


async def test_overview_and_audit_are_scoped(api):
    await _open(api, "bob", VARIANCE, {"entity": "US01", "period": "2026-09"})
    await _open(api, "alice", VARIANCE, {"entity": "UK01", "period": "2026-09"})
    alice = (await api.get("/api/overview", headers=api.as_user("alice"))).json()
    assert alice["awaiting_my_review"] == 1 and alice["open_tasks"] == 1
    assert [c["id"] for c in alice["agents"]] == ["fin.accruals", VARIANCE, "report.validation"]
    assert alice["tool_calls_24h"] > 0

    events = (await api.get("/api/audit", headers=api.as_user("alice"))).json()
    assert events and all("UK01" in e["subject"] for e in events)
    assert {e["kind"] for e in events} == {"tool_call"}
