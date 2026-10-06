"""Configurable steps (phase 1 of steps v2): a capability chains generic data
steps — dataset, dedupe, filter, convert, derive, bucket, transform, aggregate —
by configuration, each validated with the manifest and run under the same
gateway and audit. Shown on payment exceptions, the first non-finance
capability, and on variants of it."""

import copy

from agent_one_finance.capabilities import seed_files
from agent_one_finance.manifest import Manifest, problems

CAP = "payments.exceptions"
KEY = {"entity": "UK01", "date": "2026-10-05"}


def _base() -> dict:
    return next(m for m in seed_files() if m.id == CAP).model_dump(by_alias=True)


async def _open(api, key=KEY, user="paula"):
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user(user), json={"case_key": key})
    assert res.status_code == 201, res.text
    return res.json()


async def _new_version(api, manifest: dict, note: str):
    res = await api.post(f"/api/capabilities/{CAP}/versions", headers=api.as_user("paula"),
                         json={"manifest": manifest, "note": note})
    assert res.status_code == 201, res.text
    ok = await api.post(f"/api/capabilities/{CAP}/versions/{res.json()['version']}/approve", headers=api.as_user("pete"))
    assert ok.status_code == 200, ok.text


async def test_payment_exceptions_run_through_the_configured_data_steps(api):
    case = await _open(api)
    assert case["status"] == "awaiting_review", case.get("error")
    kept = [i for i in case["items"] if not i.get("excluded_by")]
    excluded = {e["by"]: e for e in case["excluded"]}
    # dedupe and filter set items aside — still on the case, with the reason
    assert excluded["dedupe_refs"]["reason"].startswith("duplicate of PX-UK01-20261005-03")
    assert excluded["drop_tests"]["reason"] == "test payment"
    assert len(kept) == 14
    # the day's FX rates are a named data set the reviewer can see
    fx = next(d for d in case["datasets"] if d["name"] == "fx")
    assert fx["source"] == "refdata.fx_rates" and fx["row_count"] == 6
    for it in kept:
        if it["currency"] == "ZAR":
            assert it["amount_gbp"] is None and it["fx_missing"] == "ZAR"     # never assumed
        else:
            assert it["amount_gbp"] == round(it["amount"] * it["fx_rate"], 2)
        assert it["sla_band"] in ("within 4h", "4–24h", "over 24h")
        assert isinstance(it["risk_score"], int)                               # the team's own service
    hours = {it["exception_id"]: it["age_hours"] for it in kept}
    first = next(it for it in kept if it["exception_id"].endswith("-01"))
    assert hours[first["exception_id"]] == round(18 - int(first["received_at"][11:13]) - int(first["received_at"][14:16]) / 60, 1)
    tools = [c["tool"] for c in case["tool_calls"]]
    assert {"payments.exceptions", "refdata.fx_rates", "payments.risk_score"} <= set(tools)   # all through the gateway
    risk_call = next(c for c in case["tool_calls"] if c["tool"] == "payments.risk_score")
    sent = risk_call["arguments"]["items"][0]
    assert set(sent) == {"item_id", "amount_gbp", "reason_code", "beneficiary_bank_bic", "channel"}  # only what it needs
    found = {g["group_key"]["reason_code"]: g["finding"] for g in case["groups"]}
    if "AC04" in found:
        assert found["AC04"]["rule"] == "closed-account"


async def test_a_step_whose_when_does_not_hold_is_skipped_and_recorded(api):
    m = _base()
    m["step_settings"]["risk"]["when"] = "case.entity == 'US01'"
    await _new_version(api, m, "score risk for US01 only")
    case = await _open(api, {"entity": "UK01", "date": "2026-10-06"})
    assert case["draft"]["skipped_steps"] == ["risk"]
    assert not any(c["tool"] == "payments.risk_score" for c in case["tool_calls"])
    assert all("risk_score" not in i for i in case["items"])


async def test_aggregate_rolls_items_up_into_a_data_set_or_the_items(api):
    m = _base()
    m["steps"].insert(m["steps"].index("group"), "by_bank")
    m["step_settings"]["by_bank"] = {"type": "aggregate", "with": {
        "by": ["beneficiary_bank_bic"], "sum": ["amount_gbp"], "into": "by_bank"}}
    await _new_version(api, m, "exposure per correspondent")
    case = await _open(api, {"entity": "UK01", "date": "2026-10-07"})
    by_bank = next(d for d in case["datasets"] if d["name"] == "by_bank")
    kept = [i for i in case["items"] if not i.get("excluded_by")]
    assert sum(r["count"] for r in by_bank["rows"]) == len(kept)
    assert {"beneficiary_bank_bic", "amount_gbp", "count"} <= set(by_bank["columns"])


def test_the_platform_checks_each_configured_step():
    m = _base()
    bad = copy.deepcopy(m)
    # a conversion before the rates it needs
    bad["steps"].remove("to_gbp")
    bad["steps"].insert(bad["steps"].index("fx"), "to_gbp")
    found = problems(Manifest.model_validate(bad))
    assert "`to_gbp` needs data set `fx`, produced by no earlier step" in found

    bad = copy.deepcopy(m)
    bad["step_settings"]["age"]["with"]["fields"]["x"] = "__import__('os')"
    bad["step_settings"]["sla"]["with"]["bands"] = []
    bad["step_settings"]["ghost"] = {"type": "derive", "with": {"fields": {}}}
    bad["step_settings"]["load"] = {"with": {"tool": "x"}}
    bad["steps"].insert(1, "mystery")
    found = problems(Manifest.model_validate(bad))
    assert any(p.startswith("step_settings.age.with.fields.x:") for p in found)
    assert any(p.startswith("step_settings.sla.with.bands:") for p in found)
    assert "step_settings.ghost: `ghost` is not in steps" in found
    assert "step_settings.load: `load` is set up in its own section, not under `with`" in found
    assert "steps: `mystery` is not a core step; give it a type under step_settings" in found


def test_tools_of_configured_steps_are_the_only_ones_allowed():
    m = Manifest.model_validate(_base())
    assert {"refdata.fx_rates", "payments.risk_score", "payments.exceptions", "payments.message_trail"} == m.tools_used() - {"ticketing.create_ticket"}


def test_existing_capabilities_need_no_change():
    for m in seed_files():
        assert problems(m) == [], (m.id, problems(m))
