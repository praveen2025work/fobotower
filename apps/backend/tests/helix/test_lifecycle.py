"""Case runs off the request path, recovery after a restart, re-run attempts,
and the review rules: required comments, maker-checker, dual review, bulk."""

import dataclasses

import pytest
from sqlalchemy import update

from helix import runner, workflow
from helix.config import settings
from helix.db import get_session
from helix.models import Case
from tests.helix.conftest import VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _open(api, user="alice", key=KEY):
    res = await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": key},
                         headers=api.as_user(user))
    assert res.status_code == 201, res.text
    return res.json()


async def _decide(api, case_id, group_id, user="alice", action="approve", comment=None, key=None):
    return await api.post(f"/api/cases/{case_id}/decisions", headers=api.as_user(user), json={
        "group_id": group_id, "action": action, "comment": comment,
        "idempotency_key": key or f"{case_id}-{group_id}-{user}-{action}"})


# ---------- background runs and recovery ----------

async def test_opening_answers_at_once_and_the_run_finishes_in_the_background(api, monkeypatch):
    background = dataclasses.replace(settings(), run_mode="background")
    monkeypatch.setattr(runner, "settings", lambda: background)
    case = await _open(api)
    assert case["status"] == "running" and case["groups"] == []
    await runner.drain()
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("alice"))).json()
    assert after["status"] == "awaiting_review" and after["groups"]


async def test_a_run_left_running_by_a_stopped_server_is_finished_on_startup(api):
    case = await _open(api)
    async with get_session() as s:      # as if the server died mid-review-resume
        await s.execute(update(Case).where(Case.case_id == case["case_id"]).values(status="running"))
        await s.commit()
    assert await runner.recover() == [case["case_id"]]
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("alice"))).json()
    assert after["status"] == "awaiting_review"


# ---------- re-run ----------

@pytest.fixture
def failing_load(monkeypatch):
    async def boom(state):
        raise RuntimeError("GL connector timed out")
    step = workflow.STEPS["load"]
    monkeypatch.setitem(workflow.STEPS, "load", dataclasses.replace(step, fn=boom))
    return lambda: monkeypatch.setitem(workflow.STEPS, "load", step)


async def test_a_failed_case_is_rerun_as_a_new_attempt_and_the_first_is_kept(api, failing_load):
    first = await _open(api)
    assert first["status"] == "failed" and "timed out" in first["error"] and first["can_rerun"]
    failing_load()                                       # the connector is back
    res = await api.post(f"/api/cases/{first['case_id']}/rerun", headers=api.as_user("alice"))
    assert res.status_code == 201, res.text
    second = res.json()
    assert second["case_id"] == f"{first['case_id']}.r2" and second["attempt"] == 2
    assert second["rerun_of"] == first["case_id"] and second["status"] == "awaiting_review"
    assert [a["status"] for a in second["attempts"]] == ["failed", "awaiting_review"]
    # opening the key again lands on the latest attempt
    assert (await _open(api))["case_id"] == second["case_id"]
    # only the latest attempt, and only a failed or escalated one, can be re-run
    again = await api.post(f"/api/cases/{first['case_id']}/rerun", headers=api.as_user("alice"))
    assert again.status_code == 409 and "newer attempt" in again.text
    live = await api.post(f"/api/cases/{second['case_id']}/rerun", headers=api.as_user("alice"))
    assert live.status_code == 409


async def test_rerun_needs_the_right_to_open_the_case(api, failing_load):
    first = await _open(api)
    failing_load()
    res = await api.post(f"/api/cases/{first['case_id']}/rerun", headers=api.as_user("viewer"))
    assert res.status_code == 404


# ---------- review rules ----------

async def test_rejecting_needs_a_reason(api):
    case = await _open(api)
    g = case["groups"][0]["group_id"]
    res = await _decide(api, case["case_id"], g, action="reject")
    assert res.status_code == 409 and "comment is required" in res.text
    assert (await _decide(api, case["case_id"], g, action="reject", comment="Wrong period")).status_code == 201


async def test_approving_an_escalated_group_needs_an_explanation(api):
    from helix import llm

    llm._adapter = llm.NoLlm()                 # every non-rule group escalates
    case = await _open(api)
    esc = next(g for g in case["groups"] if g["finding"]["status"] == "escalated")
    res = await _decide(api, case["case_id"], esc["group_id"])
    assert res.status_code == 409 and "needs your explanation" in res.text
    ok = await _decide(api, case["case_id"], esc["group_id"], comment="Accrual reversal, agreed with FP&A")
    assert ok.status_code == 201


def _with_review(monkeypatch, **review):
    """Run the variance capability with changed review settings."""
    from helix import capabilities

    real = capabilities.active

    async def active(capability_id):
        version, m = await real(capability_id)
        if capability_id == VARIANCE:
            m = m.model_copy(update={"review": m.review.model_copy(update=review)})
        return version, m
    monkeypatch.setattr(capabilities, "active", active)


async def test_maker_checker_can_stop_the_opener_signing_off(api, monkeypatch):
    _with_review(monkeypatch, opener_may_decide=False)
    case = await _open(api, user="alice")
    assert case["can_decide"] is False
    g = case["groups"][0]["group_id"]
    assert (await _decide(api, case["case_id"], g, user="alice")).status_code == 403
    assert (await _decide(api, case["case_id"], g, user="bob")).status_code == 201


async def test_large_groups_need_two_different_approvers(api, monkeypatch):
    _with_review(monkeypatch, dual_review_when="abs(total) >= 0")   # every group
    case = await _open(api, user="alice")
    cid = case["case_id"]
    for g in case["groups"]:
        await _decide(api, cid, g["group_id"], user="alice")
        await _decide(api, cid, g["group_id"], user="alice", key=f"again-{cid}-{g['group_id']}")
    still = (await api.get(f"/api/cases/{cid}", headers=api.as_user("alice"))).json()
    assert still["status"] == "awaiting_review"            # alice twice is still one person
    for g in case["groups"]:
        last = await _decide(api, cid, g["group_id"], user="bob")
    assert last.json()["case"]["status"] in ("awaiting_publish", "completed")


async def test_bulk_decide_goes_through_and_refuses_escalations_without_words(api):
    from helix import llm

    llm._adapter = llm.NoLlm()
    case = await _open(api)
    ids = [g["group_id"] for g in case["groups"]]
    escalated = {g["group_id"] for g in case["groups"] if g["finding"]["status"] == "escalated"}
    res = await api.post(f"/api/cases/{case['case_id']}/decisions/bulk", headers=api.as_user("alice"),
                         json={"group_ids": ids, "action": "approve", "idempotency_key": "bulk-key-001"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert {r["group_id"] for r in body["refused"]} == escalated
    assert {r["group_id"] for r in body["decided"]} == set(ids) - escalated
    res = await api.post(f"/api/cases/{case['case_id']}/decisions/bulk", headers=api.as_user("alice"),
                         json={"group_ids": sorted(escalated), "action": "approve",
                               "comment": "Reviewed with the desk", "idempotency_key": "bulk-key-002"})
    assert res.json()["refused"] == [] and res.json()["case"]["status"] == "awaiting_publish"


# ---------- re-investigate ----------

async def test_a_reviewer_sends_one_group_back_with_a_note(api):
    case = await _open(api)
    cid = case["case_id"]
    g = next(x for x in case["groups"] if x["finding"]["decided_by"].startswith("llm"))
    others = [x for x in case["groups"] if x["group_id"] != g["group_id"]]
    await _decide(api, cid, g["group_id"])                       # decided, then sent back
    for other in others[:-1]:
        await _decide(api, cid, other["group_id"])
    res = await api.post(f"/api/cases/{cid}/groups/{g['group_id']}/reinvestigate",
                         headers=api.as_user("alice"),
                         json={"note": "Check the October reversal", "idempotency_key": "reinv-key-1"})
    assert res.status_code == 201, res.text
    after = res.json()["case"]
    assert after["status"] == "awaiting_review"
    new = next(x for x in after["groups"] if x["group_id"] == g["group_id"])
    assert "Check the October reversal" in new["finding"]["comment"]
    assert new["finding"]["reinvestigations"] == 1 and new["finding"]["previous"]["comment"]
    # the earlier approval no longer counts: the case waits for this group again
    await _decide(api, cid, others[-1]["group_id"])
    waiting = (await api.get(f"/api/cases/{cid}", headers=api.as_user("alice"))).json()
    assert waiting["status"] == "awaiting_review"
    last = await _decide(api, cid, g["group_id"], key=f"after-{cid}")
    assert last.json()["case"]["status"] in ("awaiting_publish", "completed")


async def test_reinvestigation_is_limited_and_needs_a_note(api):
    case = await _open(api)
    cid, gid = case["case_id"], case["groups"][0]["group_id"]
    url = f"/api/cases/{cid}/groups/{gid}/reinvestigate"
    blank = await api.post(url, headers=api.as_user("alice"), json={"note": "  ", "idempotency_key": "reinv-blank"})
    assert blank.status_code == 409
    for n in range(2):
        ok = await api.post(url, headers=api.as_user("alice"), json={"note": f"look {n}", "idempotency_key": f"reinv-{n}-key"})
        assert ok.status_code == 201
    replay = await api.post(url, headers=api.as_user("alice"), json={"note": "look 1", "idempotency_key": "reinv-1-key"})
    assert replay.json()["replayed"] is True
    third = await api.post(url, headers=api.as_user("alice"), json={"note": "again", "idempotency_key": "reinv-3-key"})
    assert third.status_code == 409 and "the limit" in third.text


async def test_a_case_with_nothing_in_scope_does_not_wait_for_a_review(api, monkeypatch):
    from helix import capabilities
    real = capabilities.active

    async def active(capability_id):
        version, m = await real(capability_id)
        if capability_id == VARIANCE:     # nothing is material
            m = m.model_copy(update={"items": m.items.model_copy(update={"in_scope": "abs(variance) > 1e12"})})
        return version, m
    monkeypatch.setattr(capabilities, "active", active)
    case = await _open(api)
    assert case["groups"] == [] and case["status"] != "awaiting_review"
    assert case["status"] == "completed" and case["outcome"] == "published"   # nothing was written


# ---------- who the case waits on ----------

async def test_a_case_says_who_it_waits_on_and_why_not_the_viewer(api):
    case = await _open(api)
    assert case["waiting_on"] == {"step": "review", "roles": ["FIN_PREPARER", "FIN_REVIEWER"],
                                  "you": True, "why_not": None}
    ids = [g["group_id"] for g in case["groups"]]
    res = await api.post(f"/api/cases/{case['case_id']}/decisions/bulk", headers=api.as_user("alice"),
                         json={"group_ids": ids, "action": "approve", "comment": "Checked against the plan",
                               "idempotency_key": "waiting-on-1"})
    reviewed = res.json()["case"]
    assert reviewed["status"] == "awaiting_publish"
    mine = reviewed["waiting_on"]
    assert (mine["step"], mine["you"], mine["reviewed_by"]) == ("release", False, ["alice"])
    assert "FIN_REVIEWER" in mine["why_not"]
    bob = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("bob"))).json()
    assert bob["waiting_on"]["you"] is True and bob["publish"]["can_release"] is True
    res = await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                         json={"idempotency_key": "release-waiting-on-1"})
    done = res.json()["case"]
    assert done["waiting_on"] is None and done["publish"]["released"]["by"] == "bob"
