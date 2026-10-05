"""Team groups: one capability, configured differently by each team (rec groups)."""

import yaml

from helix.capabilities import seed_files
from helix.groups import GroupConfig, effective, set_paths
from tests.helix.conftest import CASH, FOBO, RECON

FOBO_KEY = {"book": "PRIME-MB-01", "cob": "2026-08-03"}
CASH_KEY = {"entity": "UK01", "date": "2026-10-02"}


def _recon():
    return next(m for m in seed_files() if m.id == RECON)


async def _open(api, user, group, key):
    return await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user(user),
                          json={"case_key": key, "team_group": group})


async def test_each_rec_group_runs_the_same_engine_its_own_way(api):
    fobo = (await _open(api, "frank", FOBO, FOBO_KEY)).json()
    cash = (await _open(api, "dan", CASH, CASH_KEY)).json()
    assert fobo["status"] == cash["status"] == "awaiting_review"
    assert (fobo["team_group"], cash["team_group"]) == (FOBO, CASH)
    # different sources ...
    assert {c["tool"] for c in fobo["tool_calls"] if c["requested_by"] == "match"} == {"cats.positions", "motif.positions"}
    assert {c["tool"] for c in cash["tool_calls"] if c["requested_by"] == "match"} == {"bank.statement", "ledger.postings"}
    # ... different keys, items and columns ...
    assert fobo["subject"] == "PRIME-MB-01 · COB 2026-08-03" and "cats_amount" in fobo["columns"]
    assert {i["break_type"] for i in fobo["items"]} <= {"missing_cats", "missing_motif", "amount_break"}
    # ... and the model gets the group's own tools
    assert {c["tool"] for c in fobo["tool_calls"] if c["requested_by"] == "llm"} <= {"motif.booking_events"}


async def test_a_group_only_shows_its_cases_to_its_own_people(api):
    fobo = (await _open(api, "frank", FOBO, FOBO_KEY)).json()
    assert (await api.get(f"/api/cases/{fobo['case_id']}", headers=api.as_user("dan"))).status_code == 404
    gina_scope = (await _open(api, "gina", FOBO, {"book": "PRIME-MB-02", "cob": "2026-08-03"}))
    assert gina_scope.status_code == 403                                  # data scope: one book
    dan_listed = (await api.get(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"))).json()
    assert fobo["case_id"] not in {c["case_id"] for c in dan_listed}
    # a FOBO controller sees the capability through their group
    caps = {c["id"]: c for c in (await api.get("/api/capabilities", headers=api.as_user("frank"))).json()}
    assert {g["group"] for g in caps[RECON]["groups"]} == {CASH, FOBO, "cats-motif-rates"}


async def test_a_capability_with_groups_needs_one_to_open_a_case(api):
    res = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                         json={"case_key": CASH_KEY})
    assert res.status_code == 409 and "choose a group" in res.json()["detail"]


async def test_a_case_keeps_the_exact_manifest_it_ran_on(api):
    fobo = (await _open(api, "frank", FOBO, FOBO_KEY)).json()
    detail = (await api.get(f"/api/capabilities/{RECON}/groups/{FOBO}", headers=api.as_user("frank"))).json()
    changed = {**detail["config"], "set": {**detail["config"]["set"],
                                           "policy": {**detail["config"]["set"]["policy"],
                                                      "materiality_threshold": {"value": 250000, "unit": "GBP"}}}}
    draft = await api.post(f"/api/capabilities/{RECON}/groups", headers=api.as_user("frank"),
                           json={"config": changed, "note": "Product Control confirmed materiality"})
    assert draft.status_code == 201, draft.text
    v = draft.json()["version"]
    assert (await api.post(f"/api/capabilities/{RECON}/groups/{FOBO}/versions/{v}/approve",
                           headers=api.as_user("frank"))).status_code == 403   # four-eyes
    ok = await api.post(f"/api/capabilities/{RECON}/groups/{FOBO}/versions/{v}/approve",
                        headers=api.as_user("gina"))
    assert ok.status_code == 200, ok.text
    after = (await api.get(f"/api/capabilities/{RECON}/groups/{FOBO}", headers=api.as_user("frank"))).json()
    assert after["version"] == v and after["manifest"]["policy"]["materiality_threshold"]["value"] == 250000
    again = (await api.get(f"/api/cases/{fobo['case_id']}", headers=api.as_user("frank"))).json()
    assert again["team_group_version"] == 1                                  # the old run is unchanged


async def test_a_group_cannot_change_what_the_capability_keeps(api):
    detail = (await api.get(f"/api/capabilities/{RECON}/groups/{FOBO}", headers=api.as_user("frank"))).json()
    sneaky = {**detail["config"], "set": {**detail["config"]["set"],
                                          "steps": ["match", "group", "review", "record"]}}
    res = await api.post(f"/api/capabilities/{RECON}/groups", headers=api.as_user("frank"),
                         json={"config": sneaky})
    assert res.status_code == 422
    assert any("`steps` is not configurable" in p for p in res.json()["detail"]["problems"])


async def test_only_a_groups_owners_change_it(api):
    detail = (await api.get(f"/api/capabilities/{RECON}/groups/{CASH}", headers=api.as_user("dan"))).json()
    res = await api.post(f"/api/capabilities/{RECON}/groups", headers=api.as_user("frank"),
                         json={"config": detail["config"]})
    assert res.status_code == 403


def test_group_settings_replace_at_the_configurable_path():
    base = _recon()
    cfg = GroupConfig.model_validate(yaml.safe_load(open(
        "/home/user/fobotower/config/helix/groups/recon.investigation/cats-motif.yaml")))
    m, found = effective(base, cfg)
    assert found == []
    assert m.case.scopes == {"book": "book"}                    # replaced, not merged with entity
    assert set(m.policy) == {"write_off_limit", "materiality_threshold", "posting_policy_reference",
                             "mtm_market_movement_tolerance",
                             "calculation_reasonable_tolerance"}    # policy.* merges one at a time
    allowed, refused = set_paths({"policy": {"x": {"value": 1}}, "owners": {"people": ["me"]}},
                                 base.configurable)
    assert allowed == ["policy.x"] and refused == ["owners.people"]


async def test_a_configuration_is_checked_without_being_stored(api):
    """The configuration screens check each edit as it is made; nothing is drafted."""
    cap = (await api.get(f"/api/capabilities/{RECON}", headers=api.as_user("erin"))).json()
    m = cap["manifest"]
    check = lambda body: api.post(f"/api/capabilities/{RECON}/check", headers=api.as_user("erin"), json=body)  # noqa: E731
    assert (await check({"manifest": m})).json() == {"ok": True, "problems": []}
    no_review = {**m, "steps": [s for s in m["steps"] if s != "review"]}
    found = (await check({"manifest": no_review})).json()
    assert not found["ok"] and "`review` is required" in found["problems"]
    bad_shape = {**m, "review": {**m["review"], "confirm": "maybe"}}
    assert any(p.startswith("review.confirm:") for p in (await check({"manifest": bad_shape})).json()["problems"])

    group = (await api.get(f"/api/capabilities/{RECON}/groups/{FOBO}", headers=api.as_user("frank"))).json()
    cfg = group["config"]
    assert (await check({"config": cfg})).json()["ok"]
    sneaky = {**cfg, "set": {**cfg["set"], "steps": ["match", "group", "reason", "draft", "validate", "record"]}}
    assert any("not configurable" in p for p in (await check({"config": sneaky})).json()["problems"])
    versions = (await api.get(f"/api/capabilities/{RECON}", headers=api.as_user("erin"))).json()["versions"]
    assert versions == cap["versions"]                                    # nothing was drafted
