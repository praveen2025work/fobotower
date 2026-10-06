"""Asking for evidence instead of assuming it (FOBO skill §13): a controller
asks the desk or Operations, the group waits, the answer reaches the model."""

import dataclasses
import uuid

from agent_one_finance.capabilities import seed_files
from agent_one_finance.config import settings
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.web import main

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
    # §14: the answer is what Agent One Finance shows against "What evidence did I find?"
    evidence_q = next(q for q in _group(after, "K")["checklist"] if q["id"] == "evidence")
    assert "Yes, cancelled and rebooked" in evidence_q["known"]
    ok = await api.post(f"/api/cases/{after['case_id']}/decisions", headers=api.as_user("frank"),
                        json={"group_id": aged["group_id"], "action": "approve", "comment": "Desk confirmed the rebook",
                              "checklist": [{"id": q["id"], "answer": "yes"} for q in after["review"]["checklist"]],
                              "idempotency_key": uuid.uuid4().hex})
    assert ok.status_code == 201, ok.text


async def test_at_the_tollgate_a_bot_can_answer_and_the_answer_reaches_the_model(api, monkeypatch):
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))
    case = (await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                           json={"case_key": KEY, "team_group": GROUP})).json()
    assert case["status"] == "paused_before_reason" and case["can_ask"]
    rid = (await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                          json={"target": "operations", "question": "Any MOTIF outage on the 24th?"})).json()["request_id"]
    bot = await api.post(f"/api/requests/{rid}/answer", headers={"X-AOF-Event-Secret": "evt"},
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


async def test_an_answer_can_carry_a_file_and_a_bot_gets_what_it_needs_to_reply(api, monkeypatch):
    from agent_one_finance import notify
    sent = []

    async def capture(n, link, extra=None):
        sent.append((n.kind, extra or {}))
    monkeypatch.setattr(notify, "_send_webhook", capture)
    case = await _case_at_review(api)
    aged = _group(case, "K")
    rid = (await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                          json={"target": "desk", "group_id": aged["group_id"],
                                "question": "Send the amended trade ticket"})).json()["request_id"]
    question = next(extra for kind, extra in sent if kind == "question")
    assert question["request_id"] == rid and question["answer_url"].endswith(f"/api/requests/{rid}/answer")
    assert question["answer_with_file_url"].endswith("/answer-with-file")

    res = await api.post(f"/api/requests/{rid}/answer-with-file", headers=api.as_user("tom"),
                         data={"answer": "Ticket attached"},
                         files={"file": ("ticket.pdf", b"%PDF-1.4 amended ticket", "application/pdf")})
    assert res.status_code == 200, res.text
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("frank"))).json()
    r = after["requests"][0]
    assert r["attachment"]["name"].endswith("ticket.pdf")
    kept = next(e for e in after["evidence"] if e["name"] == r["attachment"]["name"])
    assert kept["uploaded_by"] == "tom" and "answering: Send the amended trade ticket" in kept["note"]
    bad = await api.post(f"/api/requests/{rid}/answer-with-file", headers=api.as_user("tom"),
                         data={"answer": "again"}, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code in (409, 422)


async def test_unanswered_questions_are_chased_then_escalated_once(api):
    from datetime import datetime, timedelta, timezone

    from agent_one_finance import asks
    case = await _case_at_review(api)
    rid = (await api.post(f"/api/cases/{case['case_id']}/requests", headers=api.as_user("frank"),
                          json={"target": "operations", "question": "Why was the journal rejected?"})).json()["request_id"]
    now = datetime.now(timezone.utc)
    assert await asks.chase(now + timedelta(hours=1)) == []
    assert await asks.chase(now + timedelta(hours=2, minutes=5)) == [(rid, "reminded")]
    assert await asks.chase(now + timedelta(hours=3)) == []                    # once
    assert await asks.chase(now + timedelta(hours=4, minutes=5)) == [(rid, "escalated")]
    assert await asks.chase(now + timedelta(hours=9)) == []
    olga = (await api.get("/api/notifications", headers=api.as_user("olga"))).json()
    assert any(n["kind"] == "question_reminder" for n in olga["items"])
    frank = (await api.get("/api/notifications", headers=api.as_user("frank"))).json()
    assert any(n["kind"] == "question_unanswered" for n in frank["items"])
