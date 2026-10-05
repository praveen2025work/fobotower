"""FOBO on MB Rec's breaks: the matching is done upstream, Helix investigates.

The run reads MB Rec's open breaks (never CATS and MOTIF positions), settles
timing differences as MONITOR, sends aged breaks to a person, and stops at a
tollgate so the controller can approve the classification and add what the
desk said before the model is asked anything."""

import uuid

CAP, GROUP = "break.investigation", "fobo-prime"
KEY = {"book": "PRIME-MB-01", "cob": "2026-09-29"}


async def _open(api):
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                         json={"case_key": KEY, "team_group": GROUP})
    assert res.status_code == 201, res.text
    return res.json()


async def test_breaks_come_from_mb_rec_and_wait_at_the_tollgate(api):
    case = await _open(api)
    assert case["status"] == "paused_before_reason"
    tools = {c["tool"] for c in case["tool_calls"]}
    assert "mbrec.breaks" in tools
    assert not tools & {"cats.positions", "motif.positions"}               # no re-matching
    by = {i["instrument"]: i for i in case["items"]}
    assert by["UST 10Y"]["category"] == "T" and by["UST 10Y"]["side"] == "BO"   # booked late, new: timing
    assert by["IRS 5Y USD"]["category"] == "K"                                 # open 2+ COBs: aged
    assert not [c for c in case["tool_calls"] if c["requested_by"] == "llm"]    # the model has not run
    assert case["waiting_on"]["roles"] == ["FOBO_CONTROLLER"] and case["waiting_on"]["you"]


async def test_timing_is_monitored_and_the_desks_word_reaches_the_model(api):
    case = await _open(api)
    res = await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                         json={"action": "continue", "idempotency_key": uuid.uuid4().hex,
                               "comment": "Desk confirms the IRS swap was rebooked on Friday"})
    after = res.json()
    assert after["status"] == "awaiting_review", after.get("error")
    groups = {g["group_key"]["category"]: g["finding"] for g in after["groups"]}
    assert groups["T"]["verdict"] == "MONITOR" and groups["T"]["decided_by"] == "playbook"
    aged = groups["K"]
    assert aged["decided_by"].startswith("llm") and aged["sme_review"] is True
    assert "note(s) from the tollgate" in aged["comment"]
    assert after["gate_decisions"][0]["comment"] == "Desk confirms the IRS swap was rebooked on Friday"
