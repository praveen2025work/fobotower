"""Tollgates: a person approves the run's work so far before it goes on —
e.g. the computed variances before the model is asked to explain them."""

import uuid

from agent_one_finance.capabilities import seed_files
from agent_one_finance.manifest import Manifest, problems
from tests.agent_one_finance.conftest import VARIANCE

CHECK = "Are the variances complete before the model explains them?"


async def _with_gate(api) -> None:
    """Variance commentary, stopping before `reason` for a finance reviewer."""
    m = (await api.get(f"/api/capabilities/{VARIANCE}", headers=api.as_user("carol"))).json()["manifest"]
    gated = {**m, "pause_before": ["reason", "review", "publish"],
             "tollgates": {"reason": {"roles": ["FIN_REVIEWER"], "check": CHECK}}}
    res = await api.post(f"/api/capabilities/{VARIANCE}/versions", headers=api.as_user("carol"),
                         json={"manifest": gated, "note": "check variances before the model"})
    assert res.status_code == 201, res.text
    ok = await api.post(f"/api/capabilities/{VARIANCE}/versions/{res.json()['version']}/approve",
                        headers=api.as_user("bob"))
    assert ok.status_code == 200, ok.text


async def _open(api) -> dict:
    res = await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                         json={"case_key": {"entity": "UK01", "period": "2026-09"}})
    assert res.status_code == 201, res.text
    return res.json()


def _gate(api, case_id, user, action, comment=None):
    return api.post(f"/api/cases/{case_id}/gates/reason", headers=api.as_user(user),
                    json={"action": action, "comment": comment, "idempotency_key": uuid.uuid4().hex})


async def test_the_run_waits_at_the_tollgate_until_a_person_passes_it(api):
    await _with_gate(api)
    case = await _open(api)
    assert case["status"] == "paused_before_reason"
    assert case["groups"] and all(not g["finding"] for g in case["groups"])            # grouped, not yet explained
    assert not [c for c in case["tool_calls"] if c["requested_by"] == "llm"]       # the model has not run
    assert case["waiting_on"] == {"step": "gate", "gate": "reason", "roles": ["FIN_REVIEWER"], "check": CHECK,
                                  "stop_needs_comment": True, "you": False,
                                  "why_not": "passing this tollgate needs one of: FIN_REVIEWER"}

    # it is on the right desk: bob's inbox, not alice's
    bob_inbox = (await api.get("/api/inbox", headers=api.as_user("bob"))).json()
    assert [(r["case_id"], r["action"], r["gate"]) for r in bob_inbox if r["case_id"] == case["case_id"]] == [
        (case["case_id"], "gate", "reason")]
    assert case["case_id"] not in {r["case_id"] for r in (await api.get("/api/inbox", headers=api.as_user("alice"))).json()}

    assert (await _gate(api, case["case_id"], "alice", "continue")).status_code == 403   # not her gate
    res = await _gate(api, case["case_id"], "bob", "continue", "Variances tie to the ledger")
    assert res.status_code == 200, res.text
    after = res.json()
    assert after["status"] == "awaiting_review"                                         # on to the next stop
    assert [c for c in after["tool_calls"] if c["requested_by"] == "llm"]               # the model ran after the gate
    assert [(g["step"], g["action"], g["decided_by"], g["comment"]) for g in after["gate_decisions"]] == [
        ("reason", "continue", "bob", "Variances tie to the ledger")]
    again = await _gate(api, case["case_id"], "bob", "continue")
    assert again.status_code == 409                                                      # already passed


async def test_stopping_at_a_tollgate_needs_a_reason_and_ends_the_run(api):
    await _with_gate(api)
    case = await _open(api)
    assert (await _gate(api, case["case_id"], "bob", "stop")).status_code == 409         # no reason given
    res = await _gate(api, case["case_id"], "bob", "stop", "Budget file is last month's")
    after = res.json()
    assert (after["status"], after["outcome"]) == ("stopped", "stopped")
    assert "Budget file is last month's" in after["error"]
    assert after["can_rerun"] is True                                                    # a new attempt may follow
    assert not [c for c in after["tool_calls"] if c["requested_by"] == "llm"]


def test_a_tollgate_must_be_a_stop_in_the_workflow():
    m = next(x for x in seed_files() if x.id == VARIANCE).model_dump(by_alias=True)
    found = problems(Manifest.model_validate({**m, "tollgates": {"group": {"check": "x"}}}))
    assert "tollgates.group: the run does not stop before `group` (add it to pause_before)" in found
    first = problems(Manifest.model_validate({**m, "pause_before": ["load", "review", "publish"]}))
    assert any("cannot stop before its first step" in p for p in first)
    own = problems(Manifest.model_validate({**m, "tollgates": {"review": {}}}))
    assert any(p.startswith("tollgates.review:") for p in own)
