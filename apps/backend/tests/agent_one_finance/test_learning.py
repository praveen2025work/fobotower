"""Learning from the work: what nothing explained, and what could be a rule.

Configured per capability (insights.unexplained, insights.automation_after):
FOBO lists novel breaks for the skill's owners; variance commentary lists
accounts whose model commentary is approved unchanged month after month."""

import uuid

from tests.agent_one_finance.conftest import VARIANCE


async def _run_and_approve(api, period):
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                           json={"case_key": {"entity": "UK01", "period": period}})).json()
    for g in case["groups"]:
        if (g["finding"] or {}).get("status") == "proposed":
            res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("bob"),
                                 json={"group_id": g["group_id"], "action": "approve",
                                       "idempotency_key": uuid.uuid4().hex})
            assert res.status_code == 201, res.text
    return case


async def test_commentary_approved_unchanged_again_and_again_is_a_rule_candidate(api):
    cases = [await _run_and_approve(api, p) for p in ("2026-07", "2026-08", "2026-09")]
    out = (await api.get(f"/api/capabilities/{VARIANCE}/learning", headers=api.as_user("carol"))).json()
    accounts_every_month = set.intersection(*[
        {g["group_key"]["account"] for g in c["groups"]
         if (g["finding"] or {}).get("decided_by", "").startswith("llm") and g["finding"]["status"] == "proposed"}
        for c in cases])
    assert accounts_every_month, "the stub should explain at least one account every month"
    found = {a["group_key"]["account"]: a for a in out["automation"]}
    for account in accounts_every_month:
        assert found[account]["approved"] >= 3 and found[account]["rejected"] == 0
    # rule-settled groups (fx-reval) are never candidates: they already are rules
    assert not any(a["group_key"]["account"].startswith("71") for a in out["automation"])


async def test_fobo_lists_what_no_check_explained(api, monkeypatch):
    from agent_one_finance.stub_connectors import finance

    key = ("PRIME-MB-01", "2026-09-29")
    known = finance.mbrec_breaks(*key)["rows"][0]
    # A break no snapshot and no scenario explains: a novel break (H).
    novel = {**known, "instrument": "XCCY 7Y", "break_id": "MBR-NOVEL", "break_type": "amount_break",
             "age_days": 0, "journal_status": "posted", "static_present": True, "prior_adjustment": 0.0}
    monkeypatch.setitem(finance.LATE_BREAKS, key, [novel])
    case = (await api.post("/api/capabilities/break.investigation/cases", headers=api.as_user("frank"),
                           json={"case_key": {"book": key[0], "cob": key[1]}, "team_group": "fobo-prime"})).json()
    assert next(i for i in case["items"] if i["instrument"] == "XCCY 7Y")["category"] == "H"
    out = (await api.get("/api/capabilities/break.investigation/learning?team_group=fobo-prime",
                         headers=api.as_user("frank"))).json()
    expected = {i["item_id"] for i in case["items"] if i["category"] == "H" or not i.get("cause")}
    listed = {r["item_id"] for r in out["unexplained"] if r["case_id"] == case["case_id"]}
    assert "XCCY 7Y" in listed and listed == expected
    assert "no cause check explained it" in {r["why"] for r in out["unexplained_by_reason"]}
