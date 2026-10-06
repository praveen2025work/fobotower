"""The data a configuration reads and the parameters still to confirm,
derived from the configuration — for FOBO Prime (MB Rec's data contract and
Product Control's open thresholds), cash and variance commentary alike."""


async def test_fobo_primes_contract_names_mb_recs_fields_and_the_thresholds_to_confirm(api):
    res = await api.get("/api/capabilities/break.investigation/contract?team_group=fobo-prime",
                        headers=api.as_user("frank"))
    assert res.status_code == 200, res.text
    c = res.json()
    data = {d["field"]: d for d in c["data"]}
    assert "check R5" in data["book_status"]["used_by"]
    assert data["fo_prev_close_position"]["used_by"] == ["test FO-1"]
    assert data["carried_verdict"]["from"] == "follow_through" and data["carried_verdict"]["derived"]
    assert data["instrument"]["from"] == "mbrec.breaks"
    assert "motif.break_snapshots" in data["journal_status"]["from"]
    params = {p["name"]: p for p in c["parameters"]}
    assert set(c["to_confirm"]) >= {"materiality_threshold", "mtm_market_movement_tolerance"}
    assert params["mtm_market_movement_tolerance"]["used_by"] == ["test FO-4 (not run while unset)"]
    assert params["same_day_resolution_cutoff"]["used_by"] == []       # set aside for a rule not yet written


async def test_cash_and_variance_contracts_show_what_helix_computes(api):
    cash = (await api.get("/api/capabilities/recon.investigation/contract?team_group=cash-bank-ledger",
                          headers=api.as_user("dan"))).json()
    data = {d["field"]: d for d in cash["data"]}
    assert data["difference"]["from"] == "Agent One Finance: the match"
    assert cash["to_confirm"] == []
    assert {p["name"]: p["used_by"] for p in cash["parameters"]}["write_off_limit"] == ["rule small-single-break"]
    var = (await api.get("/api/capabilities/fin.variance-commentary/contract", headers=api.as_user("carol"))).json()
    assert {d["field"]: d["from"] for d in var["data"]}["variance"] == "Agent One Finance: actual − budget"


async def test_the_contract_is_for_those_who_may_see_the_capability(api):
    res = await api.get("/api/capabilities/break.investigation/contract", headers=api.as_user("carol"))
    assert res.status_code == 403
