"""Notifications: who hears about a case, only within what they may see,
read marks, and the Teams / Power Automate webhook."""

import dataclasses

from agent_one_finance import notify
from agent_one_finance.config import settings
from tests.agent_one_finance.conftest import FOBO, RECON, VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _bell(api, user):
    return (await api.get("/api/notifications", headers=api.as_user(user))).json()


async def test_reviewers_hear_a_case_needs_them_and_others_do_not(api):
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user("bob"))).json()
    alice = await _bell(api, "alice")              # FIN_PREPARER, UK01
    assert alice["unread"] == 1 and alice["items"][0]["kind"] == "review_needed"
    assert alice["items"][0]["case_id"] == case["case_id"]
    assert (await _bell(api, "frank"))["items"] == []                          # not his capability
    us = (await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("bob"),
                         json={"case_key": {"entity": "US01", "period": "2026-09"}})).json()
    assert all(n["case_id"] != us["case_id"] for n in (await _bell(api, "alice"))["items"])  # UK01 only


async def test_release_completion_and_read_marks(api):
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user("alice"))).json()
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
    bob = await _bell(api, "bob")
    assert bob["items"][0]["kind"] == "release_needed"
    await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                   json={"idempotency_key": "release-for-notify"})
    alice = await _bell(api, "alice")
    assert alice["items"][0]["kind"] == "published"
    marked = await api.post("/api/notifications/read", headers=api.as_user("alice"), json={})
    assert marked.json()["marked"] >= 2 and (await _bell(api, "alice"))["unread"] == 0


async def test_each_state_is_announced_once(api):
    await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("frank"),
                   json={"case_key": {"book": "PRIME-MB-01", "cob": "2026-08-03"}, "team_group": FOBO})
    from agent_one_finance.db import get_session
    from agent_one_finance.models import Case
    from sqlalchemy import select
    async with get_session() as s:
        case_id = (await s.execute(select(Case.case_id))).scalar_one()
    await notify.case_changed(case_id)            # announced again: no duplicate
    assert [n["kind"] for n in (await _bell(api, "gina"))["items"]] == ["review_needed"]


async def test_each_notification_is_posted_to_the_webhook(api, monkeypatch):
    sent = []

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json): sent.append((url, json))

    patched = dataclasses.replace(settings(), notify_webhook_url="https://teams.example/webhook",
                                  console_url="https://aof.internal")
    monkeypatch.setattr(notify, "settings", lambda: patched)
    monkeypatch.setattr(notify.httpx, "AsyncClient", Client)
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user("bob"))).json()
    [(url, body)] = sent
    assert url == "https://teams.example/webhook" and body["kind"] == "review_needed"
    assert body["link"] == f"https://aof.internal/cases/{case['case_id']}" and "needs your review" in body["text"]
