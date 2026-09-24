"""The Workflow tab's API."""

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from app.workflow.config import dump_config, read_workflow
from app.workflow.versions import validation_errors

ASHA = {"X-Dev-Caller": "asha"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    monkeypatch.delenv("FOBO_REASONER", raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test") as c:
        yield c


def _config(*edits) -> dict:
    raw = dump_config(read_workflow())
    for edit in edits:
        edit(raw)
    return raw


def _lookback(days):
    return _config(lambda r: r["settings"]["gather"].update(priors_lookback_days=days))


async def _draft(client, config=None, *, note="Lookback 180→90 days", based_on=1, headers=None):
    return await client.post("/api/workflow/drafts", headers=headers or {},
                             json={"config": config or _lookback(90), "note": note,
                                   "based_on": based_on})


async def _approve(client, number, *, key="k1", headers=ASHA):
    return await client.post(f"/api/workflow/versions/{number}/approve",
                             headers={"Idempotency-Key": key, **headers})


async def test_the_overview_serves_the_active_version_and_the_catalogue(client):
    body = (await client.get("/api/workflow")).json()
    assert (body["active"]["number"], body["active"]["status"]) == (1, "active")
    assert body["active"]["config"]["steps"] == read_workflow().steps
    assert [s["name"] for s in body["steps"]][:3] == ["resolve", "gather", "group"]
    assert body["settings_schema"]["gather"]["lineage_max_depth"]["max"] == 4
    assert body["reasoners"] == ["none", "session_service", "direct"]
    assert body["overrides"] == {} and body["pending_drafts"] == 0
    assert body["caller"] == {"id": "praveen", "roles": ["FO", "PC"]}
    assert [c["id"] for c in body["dev_callers"]] == ["praveen", "asha"]


async def test_outside_dev_no_dev_callers_are_offered(client, monkeypatch):
    monkeypatch.delenv("FOBO_ENV")
    assert "dev_callers" not in (await client.get("/api/workflow")).json()


async def test_a_reasoner_override_is_reported(client, monkeypatch):
    monkeypatch.setenv("FOBO_REASONER", "direct")
    assert (await client.get("/api/workflow")).json()["overrides"] == {"reasoner": "direct"}


def _move_draft_early(r):
    r["steps"].remove("draft")
    r["steps"].insert(2, "draft")


BAD = [
    (lambda r: r["steps"].remove("reason"), "'reason' cannot be removed"),
    (_move_draft_early, "'draft' needs 'pattern_groups'"),
    (lambda r: r["steps"].__setitem__(1, "gathr"), "'gathr' is not a known step"),
    (lambda r: r.update(pause_before=[]), "must include 'review'"),
    (lambda r: r["settings"]["gather"].update(prior_lookback_days=90), "prior_lookback_days"),
    # A cleared number field in the form arrives as "".
    (lambda r: r["settings"]["gather"].update(priors_lookback_days=""), "priors_lookback_days"),
]


@pytest.mark.parametrize("edit, phrase", BAD)
async def test_validate_reports_exactly_what_the_file_check_reports(client, edit, phrase):
    raw = _config(edit)
    r = await client.post("/api/workflow/validate", json={"config": raw})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["errors"] == validation_errors(raw)
    assert any(phrase in e for e in body["errors"])


async def test_a_valid_config_validates(client):
    assert (await client.post("/api/workflow/validate", json={"config": _lookback(90)})).json() == {
        "ok": True, "errors": []}


async def test_a_draft_is_created_and_counted(client):
    r = await _draft(client)
    assert r.status_code == 201
    v = r.json()
    assert (v["number"], v["status"], v["drafted_by"], v["based_on"]) == (2, "draft", "praveen", 1)
    assert (await client.get("/api/workflow")).json()["pending_drafts"] == 1


async def test_an_invalid_draft_is_a_422_listing_every_problem(client):
    r = await _draft(client, _config(lambda c: c["steps"].remove("reason"),
                                     lambda c: c["steps"].remove("validate")))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["message"] == "workflow is invalid" and len(detail["errors"]) >= 2


async def test_a_cleared_number_field_cannot_be_saved(client):
    r = await _draft(client, _config(
        lambda c: c["settings"]["gather"].update(priors_lookback_days="")))
    assert r.status_code == 422


async def test_a_draft_needs_a_note(client):
    r = await _draft(client, note="")
    assert r.status_code == 422 and "note" in r.json()["detail"]


async def test_the_drafter_cannot_approve(client):
    number = (await _draft(client)).json()["number"]
    r = await _approve(client, number, headers={})
    assert r.status_code == 403 and "second" in r.json()["detail"]


async def test_a_second_pc_user_activates_the_draft(client):
    number = (await _draft(client)).json()["number"]
    r = await _approve(client, number)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["decided_by"]) == ("active", "asha")
    overview = (await client.get("/api/workflow")).json()
    assert overview["active"]["number"] == number
    assert overview["active"]["config"]["settings"]["gather"]["priors_lookback_days"] == 90
    history = (await client.get("/api/workflow/versions")).json()
    assert [(v["number"], v["status"]) for v in history] == [(2, "active"), (1, "superseded")]
    assert "config" not in history[0]


async def test_an_approval_needs_an_idempotency_key(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/approve", headers=ASHA)
    assert r.status_code == 422


async def test_a_reused_key_is_refused(client):
    first = (await _draft(client)).json()["number"]
    await _approve(client, first, key="same")
    second = (await _draft(client, _lookback(30), based_on=first)).json()["number"]
    r = await _approve(client, second, key="same")
    assert r.status_code == 409 and "already recorded" in r.json()["detail"]


async def test_approving_twice_is_refused(client):
    number = (await _draft(client)).json()["number"]
    await _approve(client, number, key="a")
    assert (await _approve(client, number, key="b")).status_code == 409


async def test_a_stale_draft_is_refused_and_can_be_rebased(client):
    a = (await _draft(client, _lookback(90))).json()["number"]
    b = (await _draft(client, _config(lambda c: c["steps"].remove("rank")),
                      note="drop rank")).json()["number"]
    await _approve(client, a, key="ka")
    r = await _approve(client, b, key="kb")
    assert r.status_code == 409 and "v2 went live" in r.json()["detail"]
    rebased = (await client.get(f"/api/workflow/versions/{b}/rebased")).json()
    assert rebased["based_on"] == a
    assert "rank" not in rebased["config"]["steps"]
    assert rebased["config"]["settings"]["gather"]["priors_lookback_days"] == 90
    assert rebased["conflicts"] == [] and rebased["errors"] == []


async def test_only_a_draft_can_be_rebased(client):
    assert (await client.get("/api/workflow/versions/1/rebased")).status_code == 409


async def test_a_version_shows_its_changes_against_the_active_one(client):
    number = (await _draft(client)).json()["number"]
    body = (await client.get(f"/api/workflow/versions/{number}")).json()
    assert body["active_number"] == 1
    assert body["diff"] == [{"path": "settings.gather.priors_lookback_days",
                             "kind": "changed", "before": 180, "after": 90}]


async def test_a_rejection_needs_a_reason(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/reject", json={"reason": ""},
                          headers=ASHA)
    assert r.status_code == 422


async def test_a_rejection_is_recorded(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/reject",
                          json={"reason": "too aggressive"}, headers=ASHA)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["reject_reason"]) == ("rejected", "too aggressive")


async def test_an_unknown_version_is_a_404(client):
    assert (await client.get("/api/workflow/versions/99")).status_code == 404


async def test_the_yaml_download_round_trips_through_upload(client):
    r = await client.get("/api/workflow/versions/1/yaml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/yaml")
    assert 'filename="fobo-investigation-v1.yaml"' in r.headers["content-disposition"]
    up = await client.post("/api/workflow/drafts/yaml", json={"yaml": r.text, "note": "re-upload"})
    assert up.status_code == 201 and up.json()["based_on"] == 1
    assert (await client.get(f"/api/workflow/versions/{up.json()['number']}")).json()["diff"] == []


async def test_unreadable_yaml_names_the_line(client):
    r = await client.post("/api/workflow/drafts/yaml",
                          json={"yaml": "steps: [resolve,\n  gather\nname: x: y\n", "note": "bad"})
    assert r.status_code == 422
    assert r.json()["detail"]["errors"][0].startswith("line ")


async def test_an_approval_key_over_the_limit_is_a_422(client):
    number = (await _draft(client)).json()["number"]
    r = await _approve(client, number, key="k" * 129)
    assert r.status_code == 422
    assert "128" in r.json()["detail"]
