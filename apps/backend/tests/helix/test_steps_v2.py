"""Steps v2, phases 2–6, on the example capabilities: month-end accruals
(accounting actions and the authority matrix), complaint handling (time,
context, parties, outreach and a decision boundary) and a control's operating
test (sampling, child cases, waiting, attestation and a report)."""

from helix import timekeeping
from helix.stub_connectors import banking

ACCRUALS = "fin.accruals"
COMPLAINTS = "client.complaints"
CONTROLS = "controls.operating-test"


async def _open(api, cap, key, user):
    res = await api.post(f"/api/capabilities/{cap}/cases", headers=api.as_user(user), json={"case_key": key})
    assert res.status_code == 201, res.text
    return res.json()


async def _decide(api, case_id, gid, user, action="approve", key=None, checklist=None):
    return await api.post(f"/api/cases/{case_id}/decisions", headers=api.as_user(user),
                          json={"group_id": gid, "action": action, "comment": f"{action} by {user}",
                                "checklist": checklist,
                                "idempotency_key": key or f"{case_id}-{gid}-{user}-{action}"})


async def _gate(api, case_id, step, user, comment="ok"):
    res = await api.post(f"/api/cases/{case_id}/gates/{step}", headers=api.as_user(user),
                         json={"action": "continue", "comment": comment, "idempotency_key": f"{case_id}-{step}-{user}"})
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------- accruals

async def test_accruals_stop_when_the_period_is_closed(api):
    case = await _open(api, ACCRUALS, {"entity": "UK01", "period": "2026-08"}, "alice")
    assert case["status"] == "escalated"
    assert "PERIOD_CLOSED" in (case.get("error") or "") or "closed" in str(case).lower()
    assert not case["groups"]


async def test_accruals_propose_balanced_journals_within_delegated_authority(api):
    banking.POSTED.clear()
    case = await _open(api, ACCRUALS, {"entity": "UK01", "period": "2026-09"}, "alice")
    cid = case["case_id"]
    assert case["status"] == "awaiting_review"
    assert {d["name"] for d in case["datasets"]} >= {"period", "chart", "authority", "journals"}
    by_acct = {g["group_key"]["account"]: g for g in case["groups"]}
    for g in by_acct.values():
        e = g["finding"]["entries"]
        assert e["balanced"] and not e["problems"] and e["debits"] == e["credits"] > 0
        assert {ln["account"] for ln in e["lines"]} == {g["group_key"]["account"], "2150"}
    big = by_acct["6100"]                       # over 250k: two approvers, enhanced lane, never in bulk
    assert big["finding"]["authority"] == {"label": "over 250k", "roles": ["FIN_REVIEWER"], "approvals": 2,
                                           "lane": "enhanced", "bulk": False, "source": "authority"}

    # a preparer is below the matrix's authority
    refused = await _decide(api, cid, big["group_id"], "alice")
    assert refused.status_code == 403 and "authority" in refused.text

    for acct, g in by_acct.items():
        if acct != "6100":
            assert (await _decide(api, cid, g["group_id"], "bob")).status_code == 201
    # one approval is not enough above 250k; the same person twice is still one
    first = await _decide(api, cid, big["group_id"], "bob")
    assert first.status_code == 201, first.text
    assert first.json()["case"]["status"] == "awaiting_review"
    again = await _decide(api, cid, big["group_id"], "bob", key="bob-again-6100")
    assert again.status_code in (201, 403, 409)
    assert (await api.get(f"/api/cases/{cid}", headers=api.as_user("bob"))).json()["status"] == "awaiting_review"
    # a second, different reviewer settles it
    second = await _decide(api, cid, big["group_id"], "rhea")
    assert second.status_code == 201, second.text

    case = (await api.get(f"/api/cases/{cid}", headers=api.as_user("fiona"))).json()
    assert case["status"] == "awaiting_publish", case.get("error")
    assert banking.POSTED == []                  # nothing posted before release
    assert (await api.post(f"/api/cases/{cid}/publish", headers=api.as_user("bob"),
                           json={"idempotency_key": "release-by-bob"})).status_code == 403   # reviewed it
    ok = await api.post(f"/api/cases/{cid}/publish", headers=api.as_user("fiona"),
                        json={"idempotency_key": "release-by-fiona"})
    assert ok.status_code == 201, ok.text
    done = ok.json()["case"]
    assert (done["status"], done["outcome"]) == ("completed", "posted"), done.get("error")
    assert {p["journal_id"] for p in banking.POSTED} == {g["finding"]["entries"]["journal_id"] for g in by_acct.values()}
    posted = next(d for d in done["datasets"] if d["name"] == "posted")
    assert all(r["status"] == "posted" for r in posted["rows"])
    calls = [c["tool"] for c in done["tool_calls"]]
    assert calls.index("journals.validate_journal") < calls.index("journals.post_journal")   # the ledger's check first


# ---------------------------------------------------------------- complaints

async def test_complaints_bring_context_clocks_and_send_only_after_approval(api):
    banking.SENT.clear()
    key = {"entity": "UK01", "date": "2026-10-05"}
    case = await _open(api, COMPLAINTS, key, "carla")
    cid = case["case_id"]
    assert case["status"] == "paused_before_send_ack"
    assert case["waiting_on"]["gate"] == "send_ack" and case["waiting_on"]["roles"] == ["COMPLAINTS_HANDLER"]
    assert banking.SENT == []                                         # drafted, not sent
    timeline = next(d for d in case["datasets"] if d["name"] == "timeline")
    ats = [r["at"] for r in timeline["rows"]]
    assert ats == sorted(ats) and timeline["row_count"] > 0
    for it in case["items"]:
        assert it["clock_final_response_due"].endswith("Z") and it["clock_final_response_state"] in ("on time", "due soon", "breached")
        assert it["fee_correct"] == it["fee_tariff"] and it["fee_correct_ok"] == (it["fee_tariff"] == it["fee_charged"])
        assert isinstance(it["related"], list)
        if it["screen_candidate"]:                                    # a candidate only; never cleared by Helix
            assert all(c["score"] >= 0.8 for c in it["screen_candidates"])
    groups = {g["group_key"]["topic"]: g for g in case["groups"]}
    assert all(g["finding"]["draft_message"]["subject"].startswith("We have received") for g in groups.values())
    fees = groups["fees"]["finding"]
    assert fees["reserved"] == {"roles": ["COMPLAINTS_LEAD"], "reason": "redress above the handler's limit"}
    assert "Read timeline" in fees["comment"]                         # the model saw the account's timeline

    case = await _gate(api, cid, "send_ack", "carla", "acknowledgements read and fine")
    assert case["status"] == "awaiting_review", case.get("error")
    assert {m["subject"] for m in banking.SENT} == {g["finding"]["draft_message"]["subject"] for g in groups.values()}
    assert all(m["case_ref"] == cid for m in banking.SENT)
    sent = {g["group_key"]["topic"]: g["finding"]["sent_message"] for g in case["groups"]}
    assert all(s["approved_by"] == "carla" and s["message_id"] for s in sent.values())

    # redress above the limit is reserved for the lead, also in bulk
    gid = {g["group_key"]["topic"]: g["group_id"] for g in case["groups"]}
    refused = await _decide(api, cid, gid["fees"], "carla")
    assert refused.status_code == 403 and "reserved for COMPLAINTS_LEAD" in refused.text
    bulk = await api.post(f"/api/cases/{cid}/decisions/bulk", headers=api.as_user("carla"),
                          json={"group_ids": list(gid.values()), "action": "approve", "comment": "ok",
                                "idempotency_key": f"{cid}-bulk"})
    assert bulk.status_code == 201, bulk.text
    assert [d["group_id"] for d in bulk.json()["decided"]] == [gid["service"]]
    assert [r["group_id"] for r in bulk.json()["refused"]] == [gid["fees"]]
    assert (await _decide(api, cid, gid["fees"], "lena")).status_code == 201
    done = (await api.get(f"/api/cases/{cid}", headers=api.as_user("carla"))).json()
    assert done["status"] == "completed"

    # the next day, the same client's complaints link back to this case
    nxt = await _open(api, COMPLAINTS, {"entity": "UK01", "date": "2026-10-06"}, "carla")
    linked = [it for it in nxt["items"] if it["related_count"]]
    assert linked and all(r["capability_id"] == COMPLAINTS and r["on"] == "client" for it in linked for r in it["related"])
    assert all(cid in {r["case_id"] for r in it["related"]} for it in linked if it["client"] in
               {i["client"] for i in case["items"]})


async def test_clocks_warn_once_and_tell_on_breach(api):
    from datetime import datetime, timedelta, timezone
    case = await _open(api, COMPLAINTS, {"entity": "UK01", "date": "2026-10-07"}, "carla")
    due = min(datetime.fromisoformat(i["clock_final_response_due"].replace("Z", "+00:00")) for i in case["items"])
    soon = await timekeeping.check_clocks(due - timedelta(hours=1))
    assert (case["case_id"], "final_response", "clock_due_soon") in soon
    assert not [s for s in await timekeeping.check_clocks(due - timedelta(minutes=30)) if s[0] == case["case_id"]]
    late = await timekeeping.check_clocks(due + timedelta(hours=1))
    assert (case["case_id"], "final_response", "clock_breached") in late
    assert not [s for s in await timekeeping.check_clocks(due + timedelta(days=1)) if s[0] == case["case_id"]]
    bell = (await api.get("/api/notifications", headers=api.as_user("carla"))).json()
    kinds = {n["kind"] for n in (bell["items"] if isinstance(bell, dict) else bell) if n.get("case_id") == case["case_id"]}
    assert {"clock_due_soon", "clock_breached"} <= kinds
    assert datetime.now(timezone.utc)  # keep the import used


# ---------------------------------------------------------------- controls

async def test_a_control_test_samples_opens_child_cases_and_waits_for_them(api):
    case = await _open(api, CONTROLS, {"entity": "UK01", "date": "2026-10-05"}, "tess")
    cid = case["case_id"]
    assert case["status"] == "waiting_tests"
    kept = [i for i in case["items"] if not i.get("excluded_by")]
    assert len(kept) == 3 and all(i["sampled"] == "random" for i in kept)
    log = next(d for d in case["datasets"] if d["name"] == "sample")["rows"][0]
    assert log["population"] == len(case["items"]) and log["selected"] == 3 and log["seed"]
    children = next(d for d in case["datasets"] if d["name"] == "children")["rows"]
    assert len(children) == 3 and all(r["child_case_id"] for r in children)
    # a system cannot push this step on; it continues when the children finish
    pushed = await api.post(f"/api/cases/{cid}/events/tests", headers=api.as_user("tess"), json={"payload": {}})
    assert pushed.status_code in (400, 409, 422)

    for r in children:
        child = (await api.get(f"/api/cases/{r['child_case_id']}", headers=api.as_user("tess"))).json()
        assert child["case_key"]["item_ref"] == r["item_id"] and child["status"] == "awaiting_review"
        for g in child["groups"]:
            assert (await _decide(api, child["case_id"], g["group_id"], "tess")).status_code == 201
        parent = (await api.get(f"/api/cases/{cid}", headers=api.as_user("tess"))).json()
        if r is not children[-1]:
            assert parent["status"] == "waiting_tests"

    parent = (await api.get(f"/api/cases/{cid}", headers=api.as_user("owen"))).json()
    assert parent["status"] == "paused_before_attest_owner", parent.get("error")
    assert {i["child_status"] for i in parent["items"] if not i.get("excluded_by")} <= {"completed", "escalated"}
    assert parent["waiting_on"]["roles"] == ["CONTROL_OWNER"]
    assert parent["waiting_on"]["check"].startswith("I confirm the control operated")
    refused = await api.post(f"/api/cases/{cid}/gates/attest_owner", headers=api.as_user("tess"),
                             json={"action": "continue", "idempotency_key": f"{cid}-attest-tess"})
    assert refused.status_code == 403
    parent = await _gate(api, cid, "attest_owner", "owen", "attested")
    att = next(d for d in parent["datasets"] if d["name"] == "attestations")["rows"][0]
    assert att["by"] == "owen" and att["statement"].startswith("I confirm")
    assert parent["status"] in ("awaiting_review", "paused_before_review")
    if parent["status"] == "paused_before_review":
        parent = await _gate(api, cid, "review", "tess")
    for g in parent["groups"]:
        assert (await _decide(api, cid, g["group_id"], "tess")).status_code == 201
    done = (await api.get(f"/api/cases/{cid}", headers=api.as_user("tess"))).json()
    assert done["status"] == "completed", done.get("error")
    report = next(d for d in done["documents"] if d["name"].endswith("control-test-report.pdf"))
    pdf = await api.get(report["url"], headers=api.as_user("owen"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


async def test_a_wait_past_its_timeout_escalates(api):
    from datetime import datetime, timedelta, timezone

    from helix.db import get_session
    from helix.models import Case
    case = await _open(api, CONTROLS, {"entity": "UK01", "date": "2026-10-06"}, "tess")
    assert case["status"] == "waiting_tests"
    assert await timekeeping.check_waits(datetime.now(timezone.utc)) == [] or \
        case["case_id"] not in {c for c, _ in await timekeeping.check_waits(datetime.now(timezone.utc))}
    async with get_session() as s:
        c = await s.get(Case, case["case_id"])
        since = c.waiting_since
    done = await timekeeping.check_waits(since + timedelta(hours=73))
    assert (case["case_id"], "timed_out") in done
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("tess"))).json()
    assert after["status"] == "escalated" and "TIMED_OUT" in (after.get("error") or "") + str(after.get("draft"))


# ---------------------------------------------------------------- events, tiers, boundaries

PAY = "payments.exceptions"


async def _pay_version(api, change, note):
    from helix.capabilities import seed_files
    m = next(x for x in seed_files() if x.id == PAY).model_dump(by_alias=True)
    change(m)
    res = await api.post(f"/api/capabilities/{PAY}/versions", headers=api.as_user("paula"), json={"manifest": m, "note": note})
    assert res.status_code == 201, res.text
    ok = await api.post(f"/api/capabilities/{PAY}/versions/{res.json()['version']}/approve", headers=api.as_user("pete"))
    assert ok.status_code == 200, ok.text


async def test_a_run_waits_for_an_event_from_a_system_or_a_person(api, monkeypatch):
    import dataclasses

    from helix.config import settings
    from helix.web import main

    def wait_for_confirmation(m):
        m["steps"].insert(m["steps"].index("group"), "confirmed")
        m["step_settings"]["confirmed"] = {"type": "await", "label": "Beneficiary bank confirms",
                                           "with": {"event": "bank_confirmation", "timeout_hours": 24,
                                                    "roles": ["PAYMENTS_LEAD"]}}
    await _pay_version(api, wait_for_confirmation, "wait for the bank's confirmation")
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))

    case = await _open(api, PAY, {"entity": "UK01", "date": "2026-10-08"}, "paula")
    cid = case["case_id"]
    assert case["status"] == "waiting_confirmed"
    bad = await api.post(f"/api/cases/{cid}/events/confirmed", headers={"X-Helix-Event-Secret": "wrong"}, json={"payload": {}})
    assert bad.status_code == 401
    wrong_step = await api.post(f"/api/cases/{cid}/events/load", headers={"X-Helix-Event-Secret": "evt"}, json={"payload": {}})
    assert wrong_step.status_code in (400, 409, 422)
    ok = await api.post(f"/api/cases/{cid}/events/confirmed", headers={"X-Helix-Event-Secret": "evt"},
                        json={"payload": {"reference": "MT199-778", "confirmed": True}})
    assert ok.status_code == 200, ok.text
    case = (await api.get(f"/api/cases/{cid}", headers=api.as_user("paula"))).json()
    assert case["status"] == "awaiting_review", case.get("error")
    event = next(d for d in case["datasets"] if d["name"] == "event_confirmed")["rows"][0]
    assert event["reference"] == "MT199-778" and event["by"] == "system"

    # by hand: only the roles the step names
    other = await _open(api, PAY, {"entity": "UK01", "date": "2026-10-09"}, "paula")
    assert other["status"] == "waiting_confirmed"
    refused = await api.post(f"/api/cases/{other['case_id']}/events/confirmed", headers=api.as_user("pete"),
                             json={"payload": {}})
    assert refused.status_code == 403 and "PAYMENTS_LEAD" in refused.text
    by_hand = await api.post(f"/api/cases/{other['case_id']}/events/confirmed", headers=api.as_user("paula"),
                             json={"payload": {"note": "phoned the bank"}})
    assert by_hand.status_code == 200, by_hand.text


async def test_authority_tiers_in_configuration_and_a_boundary_the_model_may_not_cross(api):
    def tiers(m):
        m["review"]["authority"] = [
            {"when": "total >= 1000000", "label": "large", "roles": ["PAYMENTS_LEAD"], "approvals": 1, "lane": "enhanced", "bulk": False},
            {"label": "standard"}]
        m["boundaries"] = [{"when": "reason_code == 'AC04'", "roles": ["PAYMENTS_LEAD"],
                            "reason": "returning funds is decided by the payments lead"}]
        m["reasoning"]["reasoner"] = m["reasoning"].get("reasoner", "llm")
    await _pay_version(api, tiers, "authority tiers and a boundary")
    case = await _open(api, PAY, {"entity": "UK01", "date": "2026-10-10"}, "paula")
    for g in case["groups"]:
        f = g["finding"]
        assert f["authority"]["source"] == "configuration"
        assert f["authority"]["label"] in ("large", "standard")
        if f["authority"]["label"] == "standard":
            assert f["authority"]["roles"] == ["PAYMENTS_OPS"] and f["authority"]["bulk"] is True
        if g["group_key"].get("reason_code") == "AC04":
            assert f["reserved"]["roles"] == ["PAYMENTS_LEAD"]
            if str(f.get("decided_by", "")).startswith("llm") or f.get("withheld_proposal"):
                assert f["status"] == "escalated" and f["reason"].startswith("RESERVED")
            refused = await _decide(api, case["case_id"], g["group_id"], "pete")
            assert refused.status_code == 403 and "reserved for PAYMENTS_LEAD" in refused.text
            lead = await _decide(api, case["case_id"], g["group_id"], "paula",
                                 checklist=[{"id": q["id"], "answer": "yes"} for q in case["review"]["checklist"]])
            assert lead.status_code == 201, lead.text
    assert any(g["group_key"].get("reason_code") == "AC04" for g in case["groups"])


async def test_the_case_shows_what_it_waits_for_its_children_clocks_and_approvals(api):
    case = await _open(api, CONTROLS, {"entity": "UK01", "date": "2026-10-11"}, "tess")
    w = case["waiting_on"]
    assert (w["step"], w["event"], w["wait"], w["label"], w["you"]) == ("event", "children", "tests", "All sample tests finished", False)
    assert w["timeout_hours"] == 72 and "child case" in w["why_not"]
    assert len(case["children"]) == 3 and all(k["capability_id"] == "controls.sample-test" for k in case["children"])
    child = (await api.get(f"/api/cases/{case['children'][0]['case_id']}", headers=api.as_user("tess"))).json()
    assert child["parent_case_id"] == case["case_id"]

    c = await _open(api, COMPLAINTS, {"entity": "UK01", "date": "2026-10-12"}, "carla")
    assert [k["id"] for k in c["clocks"]] == ["final_response"] and c["clocks"][0]["label"].startswith("Final response")

    a = await _open(api, ACCRUALS, {"entity": "UK01", "period": "2026-10"}, "alice")
    big = next(g for g in a["groups"] if g["finding"]["authority"]["approvals"] == 2)
    assert big["approvals"] == {"needed": 2, "by": [], "settled": False}
    res = await _decide(api, a["case_id"], big["group_id"], "bob")
    g = next(x for x in res.json()["case"]["groups"] if x["group_id"] == big["group_id"])
    assert g["approvals"] == {"needed": 2, "by": ["bob"], "settled": False}
