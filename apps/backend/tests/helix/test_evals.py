"""Eval runs: a version tried on people's past decisions through hidden
shadow cases, scored, and kept off everyone's desk."""

from helix import llm
from tests.helix.conftest import FOBO, RECON, VARIANCE

PERIODS = ("2026-07", "2026-08")


async def _decided_cases(api):
    """Two finished lanes: everything approved by alice, released by bob."""
    for period in PERIODS:
        case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                               json={"case_key": {"entity": "UK01", "period": period}})).json()
        for g in case["groups"]:
            await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                           json={"group_id": g["group_id"], "action": "approve",
                                 "comment": "Agreed with the explanation" if g["finding"]["status"] == "escalated" else None,
                                 "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
        await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                       json={"idempotency_key": f"release-{period}"})


async def test_an_eval_replays_past_cases_hidden_and_scores_agreement(api):
    await _decided_cases(api)
    res = await api.post(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("carol"), json={"limit": 5})
    assert res.status_code == 201, res.text
    run = res.json()
    s = run["summary"]
    assert run["status"] == "done" and s["cases"] == 2 and s["groups_compared"] > 0
    assert s["agreement_rate"] is not None and 0 <= s["wording_mean"] <= 1
    assert all(r["reached"] == "awaiting_review" for r in run["results"])
    # the shadows are on nobody's desk and in no list, and told nobody
    cases = (await api.get(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("carol"))).json()
    assert len(cases) == 2 and not any(".shadow." in c["case_id"] for c in cases)
    assert not any(".shadow." in (r["case_id"] or "") for r in (await api.get("/api/inbox", headers=api.as_user("alice"))).json())
    bell = (await api.get("/api/notifications", headers=api.as_user("alice"))).json()["items"]
    assert not any(".shadow." in (n["case_id"] or "") for n in bell)
    listed = (await api.get(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("alice"))).json()
    assert [r["run_id"] for r in listed] == [run["run_id"]]


async def test_a_model_that_escalates_more_scores_lower(api):
    await _decided_cases(api)
    base = (await api.post(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("carol"), json={})).json()
    llm._adapter = llm.NoLlm()                     # "a worse model": escalates everything it cannot rule
    worse = (await api.post(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("carol"), json={})).json()
    assert worse["summary"]["escalated"] > base["summary"]["escalated"]
    assert worse["summary"]["agreement_rate"] < base["summary"]["agreement_rate"]


async def test_only_owners_start_evals_and_grouped_capabilities_name_a_group(api):
    assert (await api.post(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("alice"), json={})).status_code == 403
    no_group = await api.post(f"/api/capabilities/{RECON}/evals", headers=api.as_user("erin"), json={})
    assert no_group.status_code == 409 and "choose a team_group" in no_group.text
    ok = await api.post(f"/api/capabilities/{RECON}/evals", headers=api.as_user("frank"), json={"team_group": FOBO})
    assert ok.status_code == 201 and ok.json()["summary"]["cases"] == 0     # no decided FOBO cases yet


def test_word_overlap_judge():
    from helix.evals import _overlap
    assert _overlap("payroll accrual for October", "October payroll accrual") == 0.75
    assert _overlap("", "") == 1.0
