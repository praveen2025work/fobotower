"""Follow-through: a decision is re-tested in the next run of its series.

FOBO (skill §4 step 9, §11): after an adjustment, BO + adjustments must equal FO
on the next COB, or the investigation stays open; a MONITOR break that did not
clear is no longer "just timing". Cash: a write-off whose item is still on the
next day's run is not written off twice. Both by configuration
(`follow_through`), with the rules or playbook acting on what is carried."""

import uuid

from tests.agent_one_finance.conftest import CASH, RECON

CAP, GROUP = "break.investigation", "fobo-prime"


async def _approve_all(api, case, user):
    for g in case["groups"]:
        res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user(user),
                             json={"group_id": g["group_id"], "action": "approve", "comment": "Agreed",
                                   "confirmed": True, "idempotency_key": uuid.uuid4().hex,
                                   "checklist": [{"id": q["id"], "answer": "yes"}
                                                 for q in (case.get("review") or {}).get("checklist", [])]})
        assert res.status_code == 201, res.text
    return (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user(user))).json()


async def _fobo(api, cob):
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                         json={"case_key": {"book": "PRIME-MB-04", "cob": cob}, "team_group": GROUP})
    assert res.status_code == 201, res.text
    case = res.json()
    res = await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                         json={"action": "continue", "idempotency_key": uuid.uuid4().hex})
    assert res.json()["status"] == "awaiting_review", res.text
    return res.json()


async def test_a_monitor_that_did_not_clear_is_reopened_on_the_next_cob(api, monkeypatch):
    from agent_one_finance.stub_connectors import finance

    day1 = await _fobo(api, "2026-09-24")
    timing = next(i for i in day1["items"] if i["category"] == "T")
    assert day1["follow_through_spec"]["order_by"] == "cob"
    day1 = await _approve_all(api, day1, "frank")

    # The timing break is still open on the next COB; the others cleared.
    still = {**timing, "age_days": 1}
    still = {k: v for k, v in still.items() if not k.startswith("carried_") and k not in ("item_id", "in_scope")}
    monkeypatch.setitem(finance.LATE_BREAKS, ("PRIME-MB-04", "2026-09-25"), [still])
    day2 = await _fobo(api, "2026-09-25")
    by = {i["instrument"]: i for i in day2["items"]}
    carried = by[timing["instrument"]]
    assert (carried["carried_verdict"], carried["carried_runs"]) == ("MONITOR", 1)
    assert carried["carried_from"] == day1["subject"]
    assert (carried["cause"], carried["category"]) == ("MONITOR_NOT_CLEARED", "K")
    assert "did not clear" in carried["cause_reason"]
    assert all(not i["carried_verdict"] for n, i in by.items() if n != timing["instrument"])

    earlier = (await api.get(f"/api/cases/{day1['case_id']}", headers=api.as_user("frank"))).json()
    ft = {r["item_id"]: r for r in earlier["follow_through"]["items"]}
    assert ft[timing["item_id"]]["status"] == "still_open"
    assert ft[timing["item_id"]]["checked_in"] == day2["case_id"]
    # A POST or CORRECT_AND_REPOST is followed too; a break that is gone has cleared.
    assert earlier["follow_through"]["cleared"] >= 1
    assert {r["verdict"] for r in ft.values()} <= {"MONITOR", "POST", "CORRECT_AND_REPOST"}


def test_an_adjustment_that_did_not_clear_keeps_the_investigation_open():
    import yaml

    from agent_one_finance import rules
    from agent_one_finance.capabilities import seed_files
    from agent_one_finance.groups import GroupConfig, effective
    base = next(m for m in seed_files() if m.id == CAP)
    raw = yaml.safe_load(open(f"{__file__.rsplit('/apps/', 1)[0]}/config/agent-one-finance/groups/{CAP}/{GROUP}.yaml"))
    m, found = effective(base, GroupConfig.model_validate(raw))
    assert not found, found
    check = next(c for c in m.playbook.checks if c.id == "ADJUSTMENT_NOT_CLEARED")
    assert rules.evaluate(check.when, {"carried_verdict": "POST"})
    assert not rules.evaluate(check.when, {"carried_verdict": None})
    assert m.playbook.categories["U"].determinism == "judgement"
    assert m.playbook.verdicts["U"] == {"FO": "ESCALATE", "BO": "ESCALATE"}


async def test_cash_a_write_off_still_open_the_next_day_is_not_written_off_twice(api):
    async def run(date):
        res = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                             json={"case_key": {"entity": "UK01", "date": date}, "team_group": CASH})
        assert res.status_code == 201, res.text
        return res.json()

    day1 = await run("2026-09-29")
    stuck = next(g for g in day1["groups"] if "TX9001" in g["item_ids"])
    await _approve_all(api, {**day1, "groups": [stuck]}, "dan")

    day2 = await run("2026-09-30")
    again = next(g for g in day2["groups"] if "TX9001" in g["item_ids"])
    assert again["finding"]["rule"] == "written-off-still-open"
    assert again["finding"]["status"] == "escalated"
    assert next(i for i in day2["items"] if i["item_id"] == "TX9001")["carried_from"] == day1["subject"]
    # Day-unique references are not mistaken for yesterday's.
    assert all(not i["carried_verdict"] for i in day2["items"] if i["item_id"] != "TX9001")

    earlier = (await api.get(f"/api/cases/{day1['case_id']}", headers=api.as_user("dan"))).json()
    assert earlier["follow_through"]["still_open"] == 1


def test_follow_through_fields_must_be_in_the_case_key():
    from agent_one_finance.capabilities import seed_files
    from agent_one_finance.manifest import Manifest, problems
    base = next(m for m in seed_files() if m.id == RECON)
    bad = Manifest.model_validate({**base.model_dump(), "follow_through": {"series": ["book"], "order_by": "entity"}})
    found = problems(bad)
    assert "follow_through.series: `book` is not in case.key" in found
    bad = Manifest.model_validate({**base.model_dump(), "follow_through": {"series": ["entity"], "order_by": "entity"}})
    assert any("cannot also be in series" in p for p in problems(bad))
