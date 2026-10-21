"""Owners change an agent; a second owner approves (four-eyes)."""

from tests.agent_one_finance.conftest import VARIANCE


async def _manifest(api, user="carol"):
    return (await api.get(f"/api/agents/{VARIANCE}", headers=api.as_user(user))).json()


async def test_an_owner_drafts_and_another_owner_activates(api):
    current = await _manifest(api)
    changed = {**current["manifest"], "policy": {"materiality": {"value": 100000, "unit": "GBP"}}}
    res = await api.post(f"/api/agents/{VARIANCE}/versions", headers=api.as_user("carol"),
                         json={"manifest": changed, "note": "raise materiality"})
    assert res.status_code == 201, res.text
    version = res.json()["version"]

    own = await api.post(f"/api/agents/{VARIANCE}/versions/{version}/approve",
                         headers=api.as_user("carol"))
    assert own.status_code == 403 and "four-eyes" in own.json()["detail"]

    ok = await api.post(f"/api/agents/{VARIANCE}/versions/{version}/approve",
                        headers=api.as_user("bob"))
    assert ok.status_code == 200, ok.text
    after = await _manifest(api)
    assert after["version"] == version
    assert after["manifest"]["policy"]["materiality"]["value"] == 100000
    assert [v["status"] for v in after["versions"]] == ["active", "superseded"]


async def test_a_task_keeps_the_version_it_opened_with(api):
    task = (await api.post(f"/api/agents/{VARIANCE}/tasks", headers=api.as_user("alice"),
                           json={"task_key": {"entity": "UK01", "period": "2026-09"}})).json()
    current = (await _manifest(api))["manifest"]
    await api.post(f"/api/agents/{VARIANCE}/versions", headers=api.as_user("carol"),
                   json={"manifest": {**current, "name": "Renamed"}})
    await api.post(f"/api/agents/{VARIANCE}/versions/2/approve", headers=api.as_user("bob"))
    again = (await api.get(f"/api/tasks/{task['task_id']}", headers=api.as_user("alice"))).json()
    assert again["manifest_version"] == 1


async def test_a_non_owner_cannot_draft(api):
    current = (await _manifest(api, user="alice"))["manifest"]
    res = await api.post(f"/api/agents/{VARIANCE}/versions", headers=api.as_user("alice"),
                         json={"manifest": current})
    assert res.status_code == 403


async def test_an_invalid_change_is_refused_with_its_problems(api):
    current = (await _manifest(api))["manifest"]
    broken = {**current, "steps": [s for s in current["steps"] if s != "validate"]}
    res = await api.post(f"/api/agents/{VARIANCE}/versions", headers=api.as_user("carol"),
                         json={"manifest": broken})
    assert res.status_code == 422
    assert "`validate` is required" in res.json()["detail"]["problems"]
