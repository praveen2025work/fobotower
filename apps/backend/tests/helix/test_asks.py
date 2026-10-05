"""Asking for evidence instead of assuming it (FOBO skill §13): a controller
asks the desk or Operations, the group waits, the answer reaches the model."""

import dataclasses
import uuid

from helix.capabilities import seed_files
from helix.config import settings
from helix.manifest import Manifest, problems
from helix.web import main

CAP, GROUP = "break.investigation", "fobo-prime"
KEY = {"book": "PRIME-MB-04", "cob": "2026-09-24"}


async def _case_at_review(api):
    case = (await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                           json={"case_key": KEY, "team_group": GROUP})).json()
    res = await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                         json={"action": "continue", "idempotency_key": uuid.uuid4().hex})
    return res.json()


def _group(case, category):
    return next(g for g in case["groups"] if g["group_key"]["category"] == category)


async def test_a_question_holds_its_group_until_the_desk_answers_and_the_answer_goes_to_the_model(api):
    case = await _case_at_review(api)
    assert case["can_ask"] and [t["id"] for t in case["request_targets"]] == ["desk", "operations", "cats-support"]
    aged = _group(case, "K")
    asked = await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                           json={"target": "desk", "group_id": aged["group_id"],
                                 "question": "Was the IRS swap rebooked on Friday?"})
    assert asked.status_code == 201, asked.text
    rid = asked.json()["request_id"]

    # the group waits for the answer
    held = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"),
                          json={"group_id": aged["group_id"], "action": "approve", "comment": "ok",
                                "idempotency_key": uuid.uuid4().hex})
    assert held.status_code == 409 and "still open" in held.json()["detail"]

    # the trader sees the question and that group's breaks — not the whole case
    mine = (await api.get("/api/requests", headers=api.as_user("tom"))).json()
    assert [(q["request_id"], q["group_label"]) for q in mine] == [(rid, aged["label"])]
    assert len(mine[0]["rows"]) == len(aged["item_ids"])
    assert (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("tom"))).status_code == 404
    assert (await api.post(f"/api/requests/{rid}/answer", headers=api.as_user("olga"),
                           json={"answer": "no idea"})).status_code == 403       # not her question

    ans = await api.post(f"/api/requests/{rid}/answer", headers=api.as_user("tom"),
                         json={"answer": "Yes, cancelled and rebooked at the new rate"})
    assert ans.status_code == 200 and ans.json()["reinvestigated"] is True
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("frank"))).json()
    finding = _group(after, "K")["finding"]
    assert "Prime desk (trader) (tom) answered" in finding["reviewer_note"]          # back to the model with it
    assert after["requests"][0]["status"] == "answered"
    ok = await api.post(f"/api/cases/{after['case_id']}/decisions", headers=api.as_user("frank"),
                        json={"group_id": aged["group_id"], "action": "approve", "comment": "Desk confirmed the rebook",
                              "idempotency_key": uuid.uuid4().hex})
    assert ok.status_code == 201, ok.text


async def test_at_the_tollgate_a_bot_can_answer_and_the_answer_reaches_the_model(api, monkeypatch):
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))
    case = (await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                           json={"case_key": KEY, "team_group": GROUP})).json()
    assert case["status"] == "paused_before_reason" and case["can_ask"]
    rid = (await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                          json={"target": "operations", "question": "Any MOTIF outage on the 24th?"})).json()["request_id"]
    bot = await api.post(f"/api/requests/{rid}/answer", headers={"X-Helix-Event-Secret": "evt"},
                         json={"answer": "No outage; the overnight batch ran late", "answered_by": "olga"})
    assert bot.status_code == 200 and bot.json()["answered_by"] == "olga"
    after = (await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                            json={"action": "continue", "idempotency_key": uuid.uuid4().hex})).json()
    assert "Took into account 1 note(s)" in _group(after, "K")["finding"]["comment"]


async def test_whoever_asked_can_cancel_and_the_group_is_free_again(api):
    case = await _case_at_review(api)
    aged = _group(case, "K")
    rid = (await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                          json={"target": "desk", "group_id": aged["group_id"], "question": "?"})).json()["request_id"]
    assert (await api.post(f"/api/requests/{rid}/cancel", headers=api.as_user("tom"))).status_code == 403
    assert (await api.post(f"/api/requests/{rid}/cancel", headers=api.as_user("frank"))).json()["status"] == "cancelled"
    assert (await api.get("/api/requests", headers=api.as_user("tom"))).json() == []


def test_a_target_names_who_answers():
    m = next(x for x in seed_files() if x.id == CAP).model_dump(by_alias=True)
    found = problems(Manifest.model_validate({**m, "requests": {"targets": [{"id": "desk", "name": "Desk"}]}}))
    assert "requests.targets[desk]: name the roles or the people who answer" in found
