"""FOBO's behaviour on Agent One Finance: the CATS vs MOTIF rec group runs FOBO's playbook
(config/playbook/fobo-cats-vs-motif.yaml) as configuration — cause checks,
categories, the verdict table, the FO-never-posts guard, unset-policy
confirmation, escalation teams and book lineage as of the COB."""

import yaml

from helix import steps
from helix.capabilities import seed_files
from helix.groups import GroupConfig, effective
from tests.helix.conftest import FOBO, RECON

GROUP = "/home/user/fobotower/config/helix/groups/recon.investigation/cats-motif.yaml"


async def _run(api, book, cob, user="frank"):
    res = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user(user),
                         json={"case_key": {"book": book, "cob": cob}, "team_group": FOBO})
    assert res.status_code == 201, res.text
    return res.json()


def _fobo_manifest(**playbook_changes):
    base = next(m for m in seed_files() if m.id == RECON)
    cfg = yaml.safe_load(open(GROUP))
    cfg["set"]["playbook"] = {**cfg["set"]["playbook"], **playbook_changes}
    m, found = effective(base, GroupConfig.model_validate(cfg))
    assert found == []
    return m


async def test_every_break_gets_all_six_checks_a_category_a_side_and_its_owners(api):
    case = await _run(api, "PRIME-MB-01", "2026-08-03")
    assert case["status"] == "awaiting_review" and case["items"]
    for it in case["items"]:
        assert [c["id"] for c in it["checks"]] == ["C1", "C2", "C3", "C4", "C5", "C6"]
        positives = [c["id"] for c in it["checks"] if c["positive"]]
        assert it["cause"] == (positives[0] if positives else None)
        if not positives:       # novel, unless a validation finding explains it (FO-6 A/B)
            explained = it["test_finding"] and it["test_finding"]["id"] in ("A", "B")
            assert it["category"] == ("H" if not explained else it["category"])
        assert (it["owner_desk"], it["owner_team"]) == ("APAC-CASH", "Operations")
    assert all(g["group_key"].keys() == {"category", "side"} for g in case["groups"])


async def test_the_verdict_table_settles_proven_sides_and_judgement_goes_to_an_sme(api):
    pb = _fobo_manifest().playbook
    groups = [g for i in range(1, 13) for g in (await _run(api, f"PRIME-MB-{i:02d}", "2026-08-03"))["groups"]]
    seen = set()
    for g in groups:
        f, cat, side = g["finding"], g["group_key"]["category"], g["group_key"]["side"]
        deterministic = pb.categories[cat].determinism == "deterministic" and side in ("FO", "BO")
        if deterministic:
            table = pb.verdicts[cat][side]
            held = table == "POST" and f.get("blocked_by")          # a blocking test failed
            assert f["decided_by"] == "playbook" and f["verdict"] == (pb.blocked_verdict if held else table)
        else:
            assert f["decided_by"].startswith("llm") and f["sme_review"] is True
        assert f["escalate_to"] == pb.categories[cat].escalate_to
        if f.get("verdict") == "POST" and not f.get("blocked_by"):   # P1: thresholds unset
            assert "materiality_threshold" in f["requires_confirmation"]
        if f.get("verdict") == "ESCALATE":
            assert f["status"] == "escalated"
        seen.add(cat)
    assert "H" in seen                       # some break no check or finding explains
    novel = next(g for g in groups if g["group_key"]["category"] == "H")
    assert novel["finding"]["verdict"] == "ESCALATE" and novel["finding"]["escalate_to"] == "Product Control"


def test_an_fo_side_cause_never_posts_whatever_the_table_says():
    m = _fobo_manifest(verdicts={**_fobo_manifest().playbook.verdicts, "E": {"FO": "POST", "BO": "POST"}})
    play = {"category": "E", "side": "FO", "category_name": "Trade booking break", "escalate_to": "Desk",
            "determinism": "deterministic", "deterministic": True, "reasons": "Pending desk confirmation",
            "unset_policy": []}
    f = steps._playbook_finding(m, {"group_key": {}}, play, {"side": "FO", "category": "E"})
    assert (f["verdict"], f["status"]) == ("ESCALATE", "escalated") and f["guard"].startswith("R2")


def test_a_confirmed_threshold_clears_the_confirmation_flag():
    m = _fobo_manifest()
    play = {"category": "D", "side": "BO", "category_name": "Settlement break", "escalate_to": "Operations",
            "determinism": "deterministic", "deterministic": True, "reasons": "x", "unset_policy": []}
    f = steps._playbook_finding(m, {"group_key": {}}, play, {"side": "BO", "category": "D"})
    assert f["verdict"] == "POST" and "requires_confirmation" not in f


async def test_book_lineage_is_read_as_of_the_cob(api):
    before = await _run(api, "PRIME-MB-05", "2026-06-30")     # before the desk move
    after = await _run(api, "PRIME-MB-05", "2026-08-03")
    assert {it["owner_desk"] for it in before["items"]} == {"APAC-TREASURY"}
    assert {it["owner_desk"] for it in after["items"]} == {"APAC-CASH"}


async def test_the_cash_group_on_the_same_engine_is_unaffected(api):
    cash = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                           json={"case_key": {"entity": "UK01", "date": "2026-09-30"},
                                 "team_group": "cash-bank-ledger"})).json()
    assert cash["status"] == "awaiting_review"
    assert all("category" not in it and "checks" not in it for it in cash["items"])


# ---------- validation tests, findings, hours saved ----------

async def _book(api, i: int):
    return await _run(api, f"PRIME-MB-{i:02d}", "2026-08-03")


async def test_every_break_runs_all_fourteen_validation_tests_and_unset_thresholds_are_not_run(api):
    case = await _book(api, 1)
    for it in case["items"]:
        assert [t["id"] for t in it["tests"]] == [f"FO-{n}" for n in range(1, 9)] + [f"BO-{n}" for n in range(1, 7)]
        fo4 = next(t for t in it["tests"] if t["id"] == "FO-4")
        assert fo4["status"] == "not_run" and "mtm_market_movement_tolerance" in fo4["why"]   # P1


async def test_missing_evidence_means_not_run_never_a_pass(api):
    seen = False
    for i in range(1, 13):
        for it in (await _book(api, i))["items"]:
            bo6 = next(t for t in it["tests"] if t["id"] == "BO-6")
            if bo6["status"] == "not_run":
                assert bo6["why"] == "evidence missing: Journal status"
                seen = True
    assert seen


async def test_fo6_findings_explain_breaks_no_cause_check_did(api):
    case = await _book(api, 6)
    ins = next(it for it in case["items"] if it["test_finding"])
    assert ins["cause"] is None and ins["test_finding"]["id"] == "B"
    assert (ins["category"], ins["side"]) == ("B", "FO")                   # Pull factor break, FO side
    assert ins["cause_reason"].startswith("FO-6 finding B")


async def test_a_blocking_test_failure_holds_a_post(api):
    case = await _book(api, 4)
    g = next(g for g in case["groups"] if g["group_key"] == {"category": "D", "side": "BO"})
    f = g["finding"]
    assert (f["verdict"], f["status"]) == ("ESCALATE", "escalated")       # the table said POST
    assert f["guard"].startswith("Held: FO-1 failed") and f["blocked_by"]


async def test_hours_saved_states_its_basis(api):
    await _book(api, 1)
    o = (await api.get("/api/overview", headers=api.as_user("frank"))).json()
    h = o["hours_saved_30d"]
    assert h["value"] >= 0 and "avoided" in h["basis"] and "settled by rule or playbook" in h["basis"]


# ---------- two FOBO rec groups on one capability: Prime and Rates ----------

RATES = "cats-motif-rates"


async def test_rates_and_prime_run_the_same_playbook_with_their_own_settings(api):
    prime = await _run(api, "PRIME-MB-04", "2026-08-03")
    rates = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("rita"),
                            json={"case_key": {"book": "RATES-LDN-01", "cob": "2026-08-03"}, "team_group": RATES})).json()
    assert rates["status"] == "awaiting_review" and rates["team_group"] == RATES
    # the same playbook: every break gets the six checks and fourteen tests
    for it in rates["items"]:
        assert len(it["checks"]) == 6 and len(it["tests"]) == 14
        assert (it["owner_desk"], it["owner_team"]) == ("RATES-LDN", "Rates desk")
    # Rates' thresholds are confirmed, so a POST there is never flagged; Prime's are not
    rates_posts = [g["finding"] for g in rates["groups"] if g["finding"].get("verdict") == "POST"]
    assert all("requires_confirmation" not in f for f in rates_posts)
    prime_posts = [g["finding"] for g in prime["groups"] if g["finding"].get("verdict") == "POST" and not g["finding"].get("blocked_by")]
    assert all("requires_confirmation" in f for f in prime_posts)


async def test_each_team_sees_and_signs_off_only_its_own_books(api):
    rates = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("rita"),
                            json={"case_key": {"book": "RATES-LDN-02", "cob": "2026-08-03"}, "team_group": RATES})).json()
    # rita may not open a Prime book or a New York book; frank cannot see the Rates case
    no_prime = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("rita"),
                              json={"case_key": {"book": "PRIME-MB-01", "cob": "2026-08-03"}, "team_group": FOBO})
    assert no_prime.status_code == 403
    no_ny = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("rita"),
                           json={"case_key": {"book": "RATES-NY-01", "cob": "2026-08-03"}, "team_group": RATES})
    assert no_ny.status_code == 403
    assert (await api.get(f"/api/cases/{rates['case_id']}", headers=api.as_user("frank"))).status_code == 404
    assert rates["can_decide"] is True
    raj = (await api.get(f"/api/cases/{rates['case_id']}", headers=api.as_user("raj"))).json()
    assert raj["can_decide"] is True                        # the other Rates controller


async def test_a_rates_change_is_approved_by_the_rates_owners_only(api):
    detail = (await api.get(f"/api/capabilities/{RECON}/groups/{RATES}", headers=api.as_user("rita"))).json()
    changed = {**detail["config"], "set": {**detail["config"]["set"], "match": {**detail["config"]["set"]["match"], "tolerance": 2.0}}}
    v = (await api.post(f"/api/capabilities/{RECON}/groups", headers=api.as_user("rita"),
                        json={"config": changed, "note": "Rates tolerance 2.00"})).json()["version"]
    url = f"/api/capabilities/{RECON}/groups/{RATES}/versions/{v}/approve"
    assert (await api.post(url, headers=api.as_user("frank"))).status_code == 403   # Prime owner
    assert (await api.post(url, headers=api.as_user("rita"))).status_code == 403    # the drafter
    assert (await api.post(url, headers=api.as_user("raj"))).status_code == 200
