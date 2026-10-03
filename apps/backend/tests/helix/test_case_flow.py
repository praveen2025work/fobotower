"""A capability end to end through the API: open, review, record, learn."""

from tests.helix.conftest import RECON, VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _open(api, user="alice", capability=VARIANCE, key=KEY):
    return await api.post(f"/api/capabilities/{capability}/cases",
                          json={"case_key": key}, headers=api.as_user(user))


async def _decide(api, case_id, group_id, user="alice", action="approve", key=None):
    return await api.post(f"/api/cases/{case_id}/decisions", headers=api.as_user(user), json={
        "group_id": group_id, "action": action, "idempotency_key": key or f"{case_id}-{group_id}"})


async def test_a_case_runs_to_the_review_pause(api):
    res = await _open(api)
    assert res.status_code == 201, res.text
    case = res.json()
    assert case["status"] == "awaiting_review"
    assert case["labels"] == {"case": "Lane", "item": "Variance line"}
    assert len(case["items"]) == 14
    in_scope = [i for i in case["items"] if i["in_scope"]]
    assert in_scope and all(abs(i["variance"]) >= 50000 for i in in_scope)
    assert {g["finding"]["status"] for g in case["groups"]} == {"proposed"}
    # load through the gateway, then the model's evidence calls — all recorded
    tools = {(c["tool"], c["requested_by"]) for c in case["tool_calls"]}
    assert ("gl.balances", "load") in tools
    assert ("gl.journal_lines", "llm") in tools and ("budget.plan_lines", "llm") in tools
    assert case["can_decide"] is True


async def test_opening_the_same_key_twice_returns_the_same_case(api):
    first = (await _open(api)).json()
    second = (await _open(api, user="bob")).json()
    assert first["case_id"] == second["case_id"]
    assert second["opened_by"] == "alice"


async def test_decisions_complete_the_case_and_become_next_months_priors(api):
    case = (await _open(api)).json()
    groups = [g["group_id"] for g in case["groups"]]
    for g in groups[:-1]:
        assert (await _decide(api, case["case_id"], g)).json()["status"] == "awaiting_review"
    last = (await _decide(api, case["case_id"], groups[-1])).json()
    # recorded; the write-back now waits for a second person (tests/helix/test_publish.py)
    assert last["status"] == "awaiting_publish"
    assert last["case"]["outcome"] is None

    october = (await _open(api, key={"entity": "UK01", "period": "2026-10"})).json()
    with_priors = [g for g in october["groups"] if g["priors"]]
    assert with_priors, "approved September explanations should be October's priors"
    assert with_priors[0]["priors"][0]["case_id"] == case["case_id"]


async def test_a_replayed_decision_is_not_recorded_twice(api):
    case = (await _open(api)).json()
    g = case["groups"][0]["group_id"]
    first = (await _decide(api, case["case_id"], g, key="same-key-123")).json()
    again = (await _decide(api, case["case_id"], g, key="same-key-123")).json()
    assert first["replayed"] is False and again["replayed"] is True
    assert len(again["case"]["decisions"]) == 1


async def test_a_caller_cannot_open_a_case_outside_their_data_scope(api):
    res = await _open(api, key={"entity": "US01", "period": "2026-09"})
    assert res.status_code == 403
    assert "not entitled to entity=US01" in res.json()["detail"]


async def test_a_hidden_case_looks_exactly_like_a_missing_one(api):
    case = (await _open(api, user="bob", key={"entity": "US01", "period": "2026-09"})).json()
    hidden = await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("alice"))
    missing = await api.get("/api/cases/fin.variance-commentary.000000000000",
                            headers=api.as_user("alice"))
    assert hidden.status_code == missing.status_code == 404
    listed = (await api.get(f"/api/capabilities/{VARIANCE}/cases",
                            headers=api.as_user("alice"))).json()
    assert case["case_id"] not in {c["case_id"] for c in listed}


async def test_only_review_roles_can_decide(api):
    case = (await _open(api)).json()
    # carol owns the capability but holds no review role
    res = await _decide(api, case["case_id"], case["groups"][0]["group_id"], user="carol")
    assert res.status_code == 403


async def test_a_user_with_no_roles_sees_no_capabilities(api):
    assert (await api.get("/api/capabilities", headers=api.as_user("viewer"))).json() == []
    assert (await _open(api, user="viewer")).status_code == 403


async def test_an_unknown_user_is_refused(api):
    assert (await api.get("/api/me", headers=api.as_user("mallory"))).status_code == 403
    assert (await api.get("/api/me")).status_code == 401


async def test_a_second_capability_runs_on_the_same_platform(api):
    res = await _open(api, user="dan", capability=RECON, key={"entity": "UK01", "date": "2026-10-02"})
    case = res.json()
    assert case["status"] == "awaiting_review", res.text
    assert case["labels"] == {"case": "Rec run", "item": "Break"}
    assert {i["break_type"] for i in case["items"]} <= {"missing_bank", "missing_ledger", "amount_break"}
    tools = {(c["tool"], c["requested_by"]) for c in case["tool_calls"]}
    assert {("bank.statement", "match"), ("ledger.postings", "match")} <= tools
    # the finance user has no role on the cash capability
    assert (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("alice"))).status_code == 404
