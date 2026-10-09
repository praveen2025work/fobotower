"""FOBO on MB Rec's breaks: the matching is done upstream, Agent One Finance investigates,
following the FOBO Investigation Skill v1.0 (docs/agent-one-finance/fobo-skill/).

The run reads MB Rec's open breaks (never CATS and MOTIF positions), applies the
skill's scenario checks (R5, posting failure, static outlier, reapplication),
settles timing differences as MONITOR, sends aged breaks to a person, and stops
at a tollgate so the controller can approve the classification and add what
the desk said before the model is asked anything."""

import uuid

from agent_one_finance.config import settings
from agent_one_finance.stub_connectors import finance

CAP, GROUP = "break.investigation", "fobo-prime"


async def _open(api, book, cob):
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                         json={"case_key": {"book": book, "cob": cob}, "team_group": GROUP})
    assert res.status_code == 201, res.text
    return res.json()


async def _continue(api, case, note=None):
    res = await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                         json={"action": "continue", "comment": note, "idempotency_key": uuid.uuid4().hex})
    after = res.json()
    assert after["status"] == "awaiting_review", after.get("error")
    return after


def _findings(case):
    return {g["group_key"]["category"]: g["finding"] for g in case["groups"]}


async def test_breaks_come_from_mb_rec_and_wait_at_the_tollgate(api):
    case = await _open(api, "PRIME-MB-01", "2026-09-29")
    assert case["status"] == "paused_before_reason"
    tools = {c["tool"] for c in case["tool_calls"]}
    assert "mbrec.breaks" in tools
    assert "cats.positions" not in tools                                    # no re-matching
    # MOTIF's positions are read only to look up instrument names (near_refs), not to make breaks
    assert {c["requested_by"] for c in case["tool_calls"] if c["tool"] == "motif.positions"} <= {"bo_positions"}
    assert len(case["items"]) == len(finance.mbrec_breaks(book="PRIME-MB-01", cob="2026-09-29")["rows"])
    by = {i["instrument"]: i for i in case["items"]}
    assert by["IRS 5Y USD"]["category"] == "K"                                 # open 2+ COBs: aged
    assert by["UST 10Y"]["category"] == "F"                                    # §8 static outlier
    assert not [c for c in case["tool_calls"] if c["requested_by"] == "llm"]    # the model has not run
    assert case["waiting_on"]["roles"] == ["FOBO_CONTROLLER"] and case["waiting_on"]["you"]


async def test_timing_is_monitored_and_the_desks_word_reaches_the_model(api):
    case = await _open(api, "PRIME-MB-04", "2026-09-24")
    after = await _continue(api, case, "Desk confirms the IRS swap was rebooked on Friday")
    found = _findings(after)
    assert found["T"]["verdict"] == "MONITOR" and found["T"]["decided_by"] == "playbook"
    assert found["K"]["decided_by"].startswith("llm") and found["K"]["sme_review"] is True
    assert "note(s) from the tollgate" in found["K"]["comment"]
    assert after["gate_decisions"][0]["comment"] == "Desk confirms the IRS swap was rebooked on Friday"


async def test_the_skills_scenarios_are_settled_by_the_playbook(api):
    after = await _continue(api, await _open(api, "PRIME-MB-06", "2026-09-25"))
    by = {i["instrument"]: i for i in after["items"]}
    assert (by["IRS 10Y EUR"]["category"], by["IRS 5Y USD"]["category"], by["GILT 5Y"]["category"]) == ("R", "J", "T")
    found = _findings(after)
    assert found["R"]["verdict"] == "CORRECT_AND_REPOST"            # §8: a rejection is corrected and re-posted
    assert found["J"]["verdict"] == "POST"                          # §8: reapplication matches the carry-forward…
    assert "materiality_threshold" in found["J"]["requires_confirmation"]   # …but P1: thresholds are unset
    assert all(f["decided_by"] == "playbook" for f in (found["R"], found["J"], found["T"]))


async def test_r5_nothing_is_investigated_while_the_book_is_incomplete(api):
    after = await _continue(api, await _open(api, "PRIME-MB-06", "2026-09-22"))
    assert {i["category"] for i in after["items"]} == {"W"}
    found = _findings(after)["W"]
    assert found["verdict"] == "ESCALATE" and found["escalate_to"] == "Operations"
    assert not [c for c in after["tool_calls"] if c["requested_by"] == "llm"]


def test_a_category_settled_whatever_the_side_needs_one_verdict_for_every_side():
    import yaml

    from agent_one_finance.capabilities import seed_files
    from agent_one_finance.groups import GroupConfig, effective
    base = next(m for m in seed_files() if m.id == CAP)
    raw = yaml.safe_load(open(settings().config_dir / "groups" / CAP / f"{GROUP}.yaml"))
    raw["set"]["playbook"]["verdicts"]["W"] = {"FO": "ESCALATE", "BO": "POST"}
    _, found = effective(base, GroupConfig.model_validate(raw))
    assert "playbook.categories.W: any_side needs one verdict for every side in the table" in found


async def test_late_exceptions_open_a_follow_up_with_only_the_new_breaks(api, monkeypatch):
    import dataclasses

    from agent_one_finance.config import settings
    from agent_one_finance.stub_connectors import finance
    from agent_one_finance.web import main
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))
    key = {"book": "PRIME-MB-04", "cob": "2026-09-24"}

    async def notify():
        res = await api.post("/api/events", headers={"X-AOF-Event-Secret": "evt"},
                             json={"capability_id": CAP, "team_group": GROUP, "case_key": key})
        assert res.status_code == 201, res.text
        return (await api.get(f"/api/cases/{res.json()['case_id']}", headers=api.as_user("frank"))).json()

    day = await notify()
    assert day["follow_up_of"] is None and len(day["items"]) == 3

    nothing = await notify()                                   # MB Rec notifies again: nothing new
    assert nothing["follow_up_of"] == day["case_id"]
    assert (nothing["status"], nothing["outcome"], nothing["items"]) == ("completed", "no_new_items", [])

    first = finance.mbrec_breaks(**key)["rows"][0]
    late = {**first, "instrument": "SOFR FUT", "break_id": "MBR-LATE-1", "difference": 1250.0,
            "cats_amount": 1250.0, "motif_amount": 0.0, "age_days": 0}
    monkeypatch.setitem(finance.LATE_BREAKS, (key["book"], key["cob"]), [late])
    follow = await notify()                                    # a late exception
    assert follow["case_id"].endswith(".f2") and follow["subject"].endswith("late items 2")
    assert [i["instrument"] for i in follow["items"]] == ["SOFR FUT"]   # only the new break
    assert follow["status"] == "paused_before_reason"          # through the same tollgate

    again = (await api.get(f"/api/cases/{day['case_id']}", headers=api.as_user("frank"))).json()
    assert [f["case_id"] for f in again["follow_ups"]] == [nothing["case_id"], follow["case_id"]]
    assert [f["items"] for f in again["follow_ups"]] == [0, 1]           # the day view counts late items
    assert len(again["items"]) == 3                            # the day's case is unchanged


async def test_rates_is_a_second_group_on_the_same_capability(api):
    """FOBO Rates: the same skill, its own books, reviewers and thresholds."""
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("rita"),
                         json={"case_key": {"book": "RATES-LDN-01", "cob": "2026-09-29"}, "team_group": "fobo-rates"})
    assert res.status_code == 201, res.text
    case = res.json()
    assert case["status"] == "paused_before_reason" and case["waiting_on"]["roles"] == ["FOBO_RATES_CONTROLLER"]
    assert {c["tool"] for c in case["tool_calls"]} >= {"mbrec.breaks", "motif.break_snapshots"}
    after = (await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("rita"),
                            json={"action": "continue", "idempotency_key": uuid.uuid4().hex})).json()
    assert after["status"] == "awaiting_review", after.get("error")
    # Product Control confirmed the Rates materiality and posting policy: a POST is not flagged
    posts = [g["finding"] for g in after["groups"] if g["finding"].get("verdict") == "POST"]
    assert all(not f.get("requires_confirmation") for f in posts)
    # Rita sees London books only; FOBO Prime's controller is not a Rates reviewer
    ny = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("rita"),
                        json={"case_key": {"book": "RATES-NY-01", "cob": "2026-09-29"}, "team_group": "fobo-rates"})
    assert ny.status_code in (403, 404)
    gate = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"),
                          json={"group_id": after["groups"][0]["group_id"], "action": "approve", "comment": "x",
                                "idempotency_key": uuid.uuid4().hex})
    assert gate.status_code in (403, 404)


async def test_the_model_can_go_to_trade_level_and_a_missing_side_is_judgement(api, monkeypatch):
    """§7: CATS and MOTIF trades are the model's tools; §8: a missing side
    (not a late booking) is a judgement call, never settled by the table."""
    from agent_one_finance.stub_connectors import finance
    key = ("PRIME-MB-04", "2026-09-24")
    known = finance.mbrec_breaks(*key)["rows"][0]
    missing = {**known, "instrument": "XCCY 7Y", "break_id": "MBR-MISS", "break_type": "missing_motif",
               "motif_amount": None, "age_days": 0, "journal_status": "posted", "static_present": True,
               "prior_adjustment": 0.0}
    monkeypatch.setitem(finance.LATE_BREAKS, key, [missing])
    after = await _continue(api, await _open(api, *key))
    item = next(i for i in after["items"] if i["instrument"] == "XCCY 7Y")
    assert (item["cause"], item["category"]) == ("MISSING_SIDE", "M")
    found = _findings(after)["M"]
    assert found["decided_by"].startswith("llm") and found["sme_review"] is True
    model_tools = {c["tool"] for c in after["tool_calls"] if c["requested_by"] == "llm"}
    assert {"cats.trades", "motif.trades"} <= model_tools


async def test_algorithm_evidence_names_breaks_no_check_explained(api):
    """PRIME-MB-10 on 8 Oct: an amount booked to the wrong instrument, a split
    booking, and an instrument MOTIF holds under a typo. The algorithm steps
    add the evidence; the playbook names the category; the verdict stays a
    person's (ESCALATE), as it was for these breaks before."""
    case = await _open(api, "PRIME-MB-10", "2026-10-08")
    by = {i["instrument"]: i for i in case["items"]}
    gilt, jgb = by["GILT 5Y"], by["JGB 10Y"]
    assert gilt["offset_with"] == "JGB 10Y" and jgb["offset_with"] == "GILT 5Y"
    assert (gilt["category"], jgb["category"]) == ("O", "O") and gilt["difference"] == -jgb["difference"]
    sofr = by["SOFR FUT"]
    assert sofr["category"] == "S" and sofr["split_unique"] and len(sofr["split_members"]) == 2
    assert round(sum(m["value"] for m in sofr["split_members"]), 2) == sofr["difference"]
    irs = by["IRS 10Y EUR"]
    assert irs["break_type"] == "missing_motif" and irs["near"]
    assert [c["reference"] for c in irs["near_candidates"]] == ["IRS10Y EUR"]
    assert irs["category"] in ("N", "T")                     # a late booking (timing) is still checked first
    for i in (gilt, jgb, sofr):
        assert i["trend_points"] >= 1 and "anomaly_z" in i
    assert {gilt["determinism"], sofr["determinism"]} == {"judgement"}     # not settled by the table: model, then a person
    used = {c["requested_by"]: c["tool"] for c in case["tool_calls"]}
    assert used["history"] == "mbrec.break_history_book" and used["systemic"] == "mbrec.breaks_all"


async def test_the_same_break_in_several_books_is_one_systemic_cause(api):
    case = await _open(api, "PRIME-MB-01", "2026-10-12")
    cdx = next(i for i in case["items"] if i["instrument"] == "CDX IG")
    assert cdx["systemic"] and cdx["systemic_count"] >= 3 and cdx["category"] == "Y"
    assert "systemic_where" not in cdx                       # other books stay unnamed on this book's case
