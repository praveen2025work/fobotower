"""Eval runs: a version tried on people's past decisions through hidden
shadow cases, scored, and kept off everyone's desk."""

from agent_one_finance import llm
from tests.agent_one_finance.conftest import FOBO, RECON, VARIANCE

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
    from agent_one_finance.evals import _overlap
    assert _overlap("payroll accrual for October", "October payroll accrual") == 0.75
    assert _overlap("", "") == 1.0


async def test_a_tollgate_does_not_stop_the_hidden_copy_and_nothing_proposed_never_agrees(api, monkeypatch):
    """A capability with a tollgate before the model: the shadow runs through it to
    review, so its proposals are compared; a group with no proposal is `missing`."""
    from agent_one_finance import evals
    await _decided_cases(api)
    real = evals.runner.run_case
    seen = []

    async def spy(case_id, *a, **k):
        from agent_one_finance.db import get_session
        from agent_one_finance.models import Case
        async with get_session() as s:
            seen.append((await s.get(Case, case_id)).manifest["pause_before"])
        return await real(case_id, *a, **k)
    monkeypatch.setattr(evals.runner, "run_case", spy)
    tollgated = evals._target
    async def with_tollgate(*a, **k):
        v, gv, m = await tollgated(*a, **k)
        return v, gv, m.model_copy(update={"pause_before": ["reason", "review"]})
    monkeypatch.setattr(evals, "_target", with_tollgate)
    run = (await api.post(f"/api/capabilities/{VARIANCE}/evals", headers=api.as_user("carol"), json={})).json()
    assert seen and all(p == ["review"] for p in seen)                       # through the tollgate
    assert all(r["reached"] == "awaiting_review" for r in run["results"])
    assert run["summary"]["groups_compared"] > 0
    # scoring: grouped but nothing proposed is never counted as agreement
    assert evals.summarise([{"cost_usd": 0, "groups": [{"group": "g", "outcome": "missing"}]}])["agreement_rate"] is None


def test_escalating_what_people_approved_as_an_escalation_is_agreement():
    from agent_one_finance.evals import _outcome
    assert _outcome("approve", "escalated", same_verdict=True) == "agree"       # people approved ESCALATE
    assert _outcome("approve", "escalated") == "escalated"                     # people approved a proposal
    assert _outcome("reject", "escalated") == "agree" and _outcome("reject", "proposed") == "disagree"
