"""Learning from the work: what nothing explained, and what could be a rule.

Configured per capability (insights.unexplained, insights.automation_after):
FOBO lists novel breaks for the skill's owners; variance commentary lists
accounts whose model commentary is approved unchanged month after month."""

import uuid

from tests.helix.conftest import VARIANCE


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


async def test_fobo_lists_what_no_check_explained(api):
    opened = []
    for cob in ("2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-29"):
        opened.append((await api.post("/api/capabilities/break.investigation/cases", headers=api.as_user("frank"),
                                      json={"case_key": {"book": "PRIME-MB-01", "cob": cob},
                                            "team_group": "fobo-prime"})).json())
    out = (await api.get("/api/capabilities/break.investigation/learning?team_group=fobo-prime",
                         headers=api.as_user("frank"))).json()
    expected = {(c["case_id"], i["item_id"]) for c in opened for i in c["items"]
                if i["category"] == "H" or not i.get("cause")}
    listed = {(r["case_id"], r["item_id"]) for r in out["unexplained"]
              if r["case_id"] in {c["case_id"] for c in opened}}
    assert expected and listed == expected
    assert {r["why"] for r in out["unexplained_by_reason"]} >= {"no cause check explained it"}
