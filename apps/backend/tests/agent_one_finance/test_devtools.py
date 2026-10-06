"""Developer tools: version diffs, the instructions editor, the workflow
graph, templates, and promotion between environments."""

import dataclasses

from agent_one_finance import devtools
from agent_one_finance.config import settings
from tests.agent_one_finance.conftest import FOBO, RECON, VARIANCE


async def test_editing_instructions_drafts_a_version_whose_diff_is_only_the_skill(api):
    res = await api.post(f"/api/capabilities/{VARIANCE}/instructions", headers=api.as_user("carol"),
                         json={"skill": "Explain each variance in two sentences.", "note": "shorter"})
    assert res.status_code == 201 and res.json()["version"] == 2
    d = (await api.get(f"/api/capabilities/{VARIANCE}/versions/1/diff/2", headers=api.as_user("bob"))).json()
    assert d["changed"] == ["reasoning.skill"]
    assert "+  skill: Explain each variance in two sentences." in d["diff"]
    assert (await api.post(f"/api/capabilities/{VARIANCE}/instructions", headers=api.as_user("alice"),
                           json={"skill": "x"})).status_code == 403               # not an owner


async def test_a_group_owner_edits_their_teams_instructions(api):
    res = await api.post(f"/api/capabilities/{RECON}/instructions", headers=api.as_user("frank"),
                         json={"skill": "Check booking events first.", "team_group": FOBO})
    assert res.status_code == 201
    v = res.json()["version"]
    d = (await api.get(f"/api/capabilities/{RECON}/groups/{FOBO}/versions/1/diff/{v}",
                       headers=api.as_user("frank"))).json()
    assert d["changed"] == ["set.reasoning.skill"]


async def test_the_flow_shows_steps_gates_pauses_tools_and_people(api):
    f = (await api.get(f"/api/capabilities/{RECON}/flow?team_group={FOBO}", headers=api.as_user("frank"))).json()
    by = {n["id"]: n for n in f["nodes"]}
    assert [n["id"] for n in f["nodes"]][:4] == ["match", "enrich", "resolve", "classify"]
    assert by["match"]["tools"] == ["cats.positions", "motif.positions"]
    assert by["review"]["gate"] and by["review"]["pause"] and by["review"]["people"] == ["FOBO_CONTROLLER"]
    assert "14 validation tests" in by["classify"]["notes"] and "specialist: booking-events" in by["reason"]["notes"]
    assert f["opens"]["schedule"] == "30 6 * * 1-5" and f["edges"][0] == {"from": "match", "to": "enrich"}


async def test_templates_are_offered_for_authoring(api):
    ids = [t["id"] for t in (await api.get("/api/authoring/templates", headers=api.as_user("carol"))).json()]
    assert ids == ["attestation", "commentary", "reconciliation", "report-validation"]


async def test_a_version_is_promoted_as_a_draft_and_tampering_is_caught(api, monkeypatch):
    signed = dataclasses.replace(settings(), promotion_key="shared-uat-prod-key", env_name="uat")
    monkeypatch.setattr(devtools, "settings", lambda: signed)
    bundle = (await api.get(f"/api/capabilities/{VARIANCE}/versions/1/export", headers=api.as_user("carol"))).json()
    assert bundle["source_env"] == "uat" and bundle["signature"]
    changed = {**bundle, "content": {**bundle["content"], "name": "Sneaky"}}
    bad = await api.post("/api/promotion/import", headers=api.as_user("carol"), json={"bundle": changed})
    assert bad.status_code == 422 and "checksum mismatch" in bad.text
    unsigned = {**bundle, "signature": None}
    assert (await api.post("/api/promotion/import", headers=api.as_user("carol"),
                           json={"bundle": unsigned})).status_code == 422
    ok = await api.post("/api/promotion/import", headers=api.as_user("carol"), json={"bundle": bundle})
    assert ok.status_code == 201
    assert ok.json()["version"] == 2 and ok.json()["note"].startswith("promoted from uat v1")
    caps = (await api.get(f"/api/capabilities/{VARIANCE}", headers=api.as_user("carol"))).json()
    assert caps["version"] == 1                    # still a draft here until another owner approves
