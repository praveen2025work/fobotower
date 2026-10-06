"""Authoring either way: a model drafts from a BRD when one is connected, or
an author answers a guided form with no model. Both are judged by the same
validator, and neither goes live before another owner approves it."""


async def _guided(api, answers, user="erin"):
    res = await api.post("/api/authoring/guided", headers=api.as_user(user), json=answers)
    assert res.status_code == 200, res.text
    return res.json()


async def test_modes_say_what_is_offered_without_a_model(api):
    modes = (await api.get("/api/authoring/modes", headers=api.as_user("erin"))).json()
    assert modes["guided"] and modes["templates"]
    assert modes["brd_model"] is False and "No model is connected" in modes["brd_note"]   # tests run on the stub


async def test_a_reconciliation_from_answers_passes_every_check(api):
    out = await _guided(api, {
        "name": "Cash — bank vs ledger (EU)", "kind": "reconcile", "case_key": ["entity", "date"], "scope_field": "entity",
        "left_tool": "bank.statement", "right_tool": "ledger.postings", "match_keys": ["ref"], "amount_field": "amount",
        "left_label": "bank", "right_label": "ledger", "group_by": ["counterparty"], "reviewer_roles": ["CASH_OPS"],
        "decided_by": "model_then_person", "model_tools": ["ledger.counterparty_history"],
        "checklist": ["Is each write-off within policy?"], "follow_through": True})
    assert out["problems"] == [], out["problems"]
    m = out["manifest"]
    assert m["steps"][:2] == ["match", "group"] and m["match"]["left"]["args"] == {"entity": "$case.entity", "date": "$case.date"}
    assert m["follow_through"] == {"series": ["entity"], "order_by": "date", "verdicts": []}
    assert m["review"]["checklist"][0]["label"] == "Is each write-off within policy?"
    assert out["author"] == "guided"
    sub = await api.post("/api/authoring/submit", headers=api.as_user("erin"), json={"yaml": out["yaml"], "note": "guided"})
    assert sub.status_code == 201, sub.text


async def test_investigating_breaks_with_a_tollgate_and_no_model(api):
    out = await _guided(api, {
        "name": "Equities breaks", "kind": "investigate", "case_key": ["book", "cob"], "scope_field": "book",
        "source_tool": "mbrec.breaks", "id_field": "instrument", "amount_field": "difference",
        "group_by": ["break_type"], "reviewer_roles": ["FOBO_CONTROLLER"], "decided_by": "person",
        "tollgate": True, "opens": "event", "late_items": True,
        "ask_targets": [{"name": "Equities desk", "roles": ["EQ_DESK"]}]})
    assert out["problems"] == [], out["problems"]
    m = out["manifest"]
    assert m["reasoning"]["reasoner"] == "none" and m["pause_before"] == ["reason", "review"]
    assert m["case"]["late_items"] == "follow_up" and m["requests"]["targets"][0]["id"] == "equities-desk"
    assert any("No model" in a for a in out["assumptions"])


async def test_commentary_with_unconfirmed_materiality(api):
    out = await _guided(api, {"name": "Cost centre commentary", "kind": "commentary", "case_key": ["entity", "period"],
                              "source_tool": "gl.balances", "id_field": "line_id", "amount_field": "variance",
                              "materiality": 25000, "unit": "GBP", "group_by": ["account"], "reviewer_roles": ["FIN_REVIEWER"]})
    assert out["problems"] == [], out["problems"]
    assert out["manifest"]["items"]["in_scope"] == "abs(variance) >= policy.materiality"


async def test_what_is_missing_comes_back_as_problems_not_errors(api):
    out = await _guided(api, {"name": "x", "kind": "reconcile", "left_tool": "bank.statement"})
    assert "a reconciliation needs both systems' tools" in out["problems"]
    assert any("YOUR_REVIEWER_ROLE" in a for a in out["assumptions"])
