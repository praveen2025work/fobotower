"""Run-the-bank controls: off switches (capability, group, connector) and
model spend limits."""

import pytest

from agent_one_finance import controls, llm
from tests.agent_one_finance.conftest import CASH, FOBO, RECON, VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


@pytest.fixture(autouse=True)
def fresh_cache():
    controls._cache.clear()
    yield
    controls._cache.clear()


async def _switch(api, user, kind, target, off, reason="maintenance window"):
    return await api.post("/api/switches", headers=api.as_user(user),
                          json={"kind": kind, "target": target, "off": off, "reason": reason})


async def _open(api, user="alice", cap=VARIANCE, key=KEY, group=None):
    return await api.post(f"/api/capabilities/{cap}/cases", headers=api.as_user(user),
                          json={"case_key": key, "team_group": group})


async def test_a_capability_switched_off_opens_nothing_until_switched_on(api):
    assert (await _switch(api, "alice", "capability", VARIANCE, True)).status_code == 403   # not an owner
    assert (await _switch(api, "carol", "capability", VARIANCE, True, reason="")).status_code == 422
    assert (await _switch(api, "carol", "capability", VARIANCE, True)).status_code == 200
    refused = await _open(api)
    assert refused.status_code == 409 and "switched off: maintenance window" in refused.text
    await _switch(api, "carol", "capability", VARIANCE, False)
    assert (await _open(api)).status_code == 201
    [sw] = (await api.get("/api/switches", headers=api.as_user("carol"))).json()
    assert [h["off"] for h in sw["history"]] == [True, False] and sw["can_switch"] is True


async def test_a_group_owner_switches_their_team_off_without_touching_others(api):
    assert (await _switch(api, "frank", "group", f"{RECON}/{FOBO}", True)).status_code == 200
    fobo = await _open(api, "frank", RECON, {"book": "PRIME-MB-01", "cob": "2026-08-03"}, FOBO)
    assert fobo.status_code == 409
    cash = await _open(api, "dan", RECON, {"entity": "UK01", "date": "2026-09-30"}, CASH)
    assert cash.status_code == 201


async def test_platform_support_switches_a_connector_and_every_call_to_it_is_refused(api):
    assert (await _switch(api, "carol", "connector", "gl", True)).status_code == 403
    assert (await _switch(api, "pat", "connector", "gl", True, reason="GL outage INC-4411")).status_code == 200
    case = (await _open(api)).json()
    assert case["status"] == "escalated" and "switched off: GL outage INC-4411" in case["error"]
    refused = [t for t in case["tool_calls"] if not t["allowed"]]
    assert refused and refused[0]["tool"] == "gl.balances"                       # audited as refused


async def test_switching_a_capability_off_mid_review_stops_the_write_back(api):
    case = (await _open(api)).json()
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"{case['case_id']}-{g['group_id']}"})   # decisions still land
    await _switch(api, "carol", "capability", VARIANCE, True, reason="reporting freeze")
    done = (await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                           json={"idempotency_key": "release-in-freeze"})).json()["case"]
    assert done["outcome"] == "publish_failed" and "reporting freeze" in done["error"]


class _Costly(llm.StubLlm):
    async def reason(self, request, tools):
        res = await super().reason(request, tools)
        return llm.ReasonResult(status=res.status, comment=res.comment, model="costly", usage={"cost_usd": 3.0})


async def test_over_the_case_limit_groups_go_to_a_person_not_the_model(api):
    llm._adapter = _Costly()              # $3 a group; the case limit is $5
    case = (await _open(api)).json()
    by_model = [g for g in case["groups"] if g["finding"]["decided_by"].startswith("llm")]
    over = [g for g in case["groups"] if "BUDGET_EXCEEDED" in (g["finding"]["reason"] or "")]
    assert len(by_model) == 2 and over
    assert over[0]["finding"]["status"] == "escalated" and "of its $5.00" in over[0]["finding"]["reason"]
    assert await controls.spent(VARIANCE, case_id=case["case_id"]) == 6.0
    ans = (await api.post(f"/api/cases/{case['case_id']}/ask", headers=api.as_user("alice"),
                          json={"question": "status?"})).json()["answer"]
    assert "No model: BUDGET_EXCEEDED" in ans["text"]
