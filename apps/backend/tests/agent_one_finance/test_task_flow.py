"""An agent end to end through the API: open, review, record, learn."""

from tests.agent_one_finance.conftest import CASH, RECON, VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _open(api, user="alice", agent=VARIANCE, key=KEY, group=None):
    return await api.post(f"/api/agents/{agent}/tasks",
                          json={"task_key": key, "team_group": group}, headers=api.as_user(user))


async def _decide(api, task_id, group_id, user="alice", action="approve", key=None):
    return await api.post(f"/api/tasks/{task_id}/decisions", headers=api.as_user(user), json={
        "group_id": group_id, "action": action, "idempotency_key": key or f"{task_id}-{group_id}"})


async def test_a_task_runs_to_the_review_pause(api):
    res = await _open(api)
    assert res.status_code == 201, res.text
    task = res.json()
    assert task["status"] == "awaiting_review"
    assert task["labels"] == {"task": "Lane", "item": "Variance line", "agent": "P&L variance commentary"}
    assert len(task["items"]) == 14
    in_scope = [i for i in task["items"] if i["in_scope"]]
    assert in_scope and all(abs(i["variance"]) >= 50000 for i in in_scope)
    assert {g["finding"]["status"] for g in task["groups"]} == {"proposed"}
    # load through the gateway, then the model's evidence calls — all recorded
    tools = {(c["tool"], c["requested_by"]) for c in task["tool_calls"]}
    assert ("gl.balances", "load") in tools
    assert ("gl.journal_lines", "llm") in tools and ("budget.plan_lines", "llm") in tools
    assert task["can_decide"] is True


async def test_opening_the_same_key_twice_returns_the_same_task(api):
    first = (await _open(api)).json()
    second = (await _open(api, user="bob")).json()
    assert first["task_id"] == second["task_id"]
    assert second["opened_by"] == "alice"


async def test_decisions_complete_the_task_and_become_next_months_priors(api):
    task = (await _open(api)).json()
    groups = [g["group_id"] for g in task["groups"]]
    for g in groups[:-1]:
        assert (await _decide(api, task["task_id"], g)).json()["status"] == "awaiting_review"
    last = (await _decide(api, task["task_id"], groups[-1])).json()
    # recorded; the write-back now waits for a second person (tests/agent_one_finance/test_publish.py)
    assert last["status"] == "awaiting_publish"
    assert last["task"]["outcome"] is None

    october = (await _open(api, key={"entity": "UK01", "period": "2026-10"})).json()
    with_priors = [g for g in october["groups"] if g["priors"]]
    assert with_priors, "approved September explanations should be October's priors"
    assert with_priors[0]["priors"][0]["task_id"] == task["task_id"]


async def test_a_replayed_decision_is_not_recorded_twice(api):
    task = (await _open(api)).json()
    g = task["groups"][0]["group_id"]
    first = (await _decide(api, task["task_id"], g, key="same-key-123")).json()
    again = (await _decide(api, task["task_id"], g, key="same-key-123")).json()
    assert first["replayed"] is False and again["replayed"] is True
    assert len(again["task"]["decisions"]) == 1


async def test_a_caller_cannot_open_a_task_outside_their_data_scope(api):
    res = await _open(api, key={"entity": "US01", "period": "2026-09"})
    assert res.status_code == 403
    assert "not entitled to entity=US01" in res.json()["detail"]


async def test_a_hidden_task_looks_exactly_like_a_missing_one(api):
    task = (await _open(api, user="bob", key={"entity": "US01", "period": "2026-09"})).json()
    hidden = await api.get(f"/api/tasks/{task['task_id']}", headers=api.as_user("alice"))
    missing = await api.get("/api/tasks/fin.variance-commentary.000000000000",
                            headers=api.as_user("alice"))
    assert hidden.status_code == missing.status_code == 404
    listed = (await api.get(f"/api/agents/{VARIANCE}/tasks",
                            headers=api.as_user("alice"))).json()
    assert task["task_id"] not in {c["task_id"] for c in listed}


async def test_only_review_roles_can_decide(api):
    task = (await _open(api)).json()
    # carol owns the agent but holds no review role
    res = await _decide(api, task["task_id"], task["groups"][0]["group_id"], user="carol")
    assert res.status_code == 403


async def test_a_user_with_no_roles_sees_no_agents(api):
    assert (await api.get("/api/agents", headers=api.as_user("viewer"))).json() == []
    assert (await _open(api, user="viewer")).status_code == 403


async def test_an_unknown_user_is_refused(api):
    assert (await api.get("/api/me", headers=api.as_user("mallory"))).status_code == 403
    assert (await api.get("/api/me")).status_code == 401


async def test_a_second_agent_runs_on_the_same_platform(api):
    res = await _open(api, user="dan", agent=RECON, key={"entity": "UK01", "date": "2026-10-02"},
                      group=CASH)
    task = res.json()
    assert task["status"] == "awaiting_review", res.text
    assert task["labels"] == {"task": "Bank vs ledger", "item": "Break", "agent": "Helix FOBO Agent"}
    assert {i["break_type"] for i in task["items"]} <= {"missing_bank", "missing_ledger", "amount_break"}
    tools = {(c["tool"], c["requested_by"]) for c in task["tool_calls"]}
    assert {("bank.statement", "match"), ("ledger.postings", "match")} <= tools
    # the finance user has no role on the cash agent
    assert (await api.get(f"/api/tasks/{task['task_id']}", headers=api.as_user("alice"))).status_code == 404
