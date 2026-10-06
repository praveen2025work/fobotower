"""Steps v2 step types on their own: each run against a small state, with
storage and tool calls replaced, so what a type does is plain to read."""

import pytest

from agent_one_finance import stepkit, steps_v2
from agent_one_finance.capabilities import seed_files
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.workflow import order_problems

BASE = next(m for m in seed_files() if m.id == "payments.exceptions")


@pytest.fixture
def lab(monkeypatch):
    saved, datasets, excluded, calls, tools = [], {}, [], [], {}

    async def save(state, items):
        saved.append(items)

    async def keep(state, step_id, name, source, rows):
        datasets[name] = rows

    async def exclude(state, step_id, items, reason):
        excluded.extend({**i, "excluded_reason": reason} for i in items)

    async def call(state, step_id, tool, args, *, write_by=None):
        calls.append((tool, args))
        return tools[tool](args) if callable(tools[tool]) else tools[tool]

    for name, fn in (("_save", save), ("_keep_dataset", keep), ("_exclude", exclude), ("_call", call)):
        monkeypatch.setattr(steps_v2, name, fn)

    class Lab:
        def state(self, items, **extra):
            return {"case_id": "lab-1", "case_key": {"entity": "UK01", "date": "2026-10-05", "period": "2026-09"},
                    "manifest": BASE.model_dump(by_alias=True), "items": items, **extra}

        async def run(self, type_name, cfg, state, step_id="step"):
            t = stepkit.TYPES[type_name]
            return await t.run(state, t.config.model_validate(cfg), step_id)

    lab = Lab()
    lab.datasets, lab.excluded, lab.calls, lab.tools = datasets, excluded, calls, tools
    return lab


# ---------- phase 2: accounting actions

async def test_recompute_by_formula_never_assumes_right(lab):
    out = await lab.run("recompute", {"formula": "round(balance * rate / 365, 2)", "compare_to": "interest", "as": "expected"},
                        lab.state([{"item_id": "a", "balance": 36500, "rate": 0.05, "interest": 5.0},
                                   {"item_id": "b", "balance": 36500, "rate": 0.05, "interest": 4.0},
                                   {"item_id": "c", "balance": None, "rate": 0.05, "interest": 4.0}]))
    a, b, c = out["items"]
    assert (a["expected"], a["expected_ok"]) == (5.0, True)
    assert (b["expected_difference"], b["expected_ok"]) == (1.0, False)
    assert c["expected"] is None and c["expected_ok"] is None and c["recompute_error"]


async def test_schedule_spreads_and_the_last_period_takes_the_rounding(lab):
    out = await lab.run("schedule", {"amount": "amount", "periods": 3, "start": "first", "into": "release"},
                        lab.state([{"item_id": "p", "amount": 100.0, "first": "2026-11"}]))
    rows = out["datasets"]["release"]
    assert [r["period"] for r in rows] == ["2026-11", "2026-12", "2027-01"]
    assert [r["amount"] for r in rows] == [33.33, 33.33, 33.34] and sum(r["amount"] for r in rows) == 100.0


# ---------- phase 3: assurance

HISTORY = [{"account": "6100", "value": v} for v in (100, 110, 90, 100)] + [{"account": "6200", "value": 50}]


async def test_flux_and_anomaly_compare_each_item_with_its_own_history(lab):
    st = lab.state([{"item_id": "x", "account": "6100", "amount": 200}, {"item_id": "y", "account": "6300", "amount": 5}],
                   datasets={"history": HISTORY})
    flux = (await lab.run("flux", {"history": "history", "key": "account", "value": "amount"}, st))["items"]
    assert (flux[0]["flux_baseline"], flux[0]["flux_change"], flux[0]["flux_pct"]) == (100.0, 100.0, 100.0)
    assert flux[0]["flux_z"] > 10 and flux[1]["flux_change"] is None          # no history: shown, never zero
    anomaly = (await lab.run("anomaly", {"history": "history", "key": "account", "value": "amount", "threshold": 3}, st))["items"]
    assert anomaly[0]["anomaly"] is True and anomaly[1]["anomaly"] is False and anomaly[1]["anomaly_z"] is None


async def test_consistency_turns_each_failing_check_into_an_item(lab):
    st = lab.state([{"item_id": "i1", "amount": 60}, {"item_id": "i2", "amount": 40}],
                   datasets={"gl": [{"account": "1000", "balance": 100}, {"account": "2000", "balance": 7}]})
    out = await lab.run("consistency", {"checks": [
        {"id": "subledger", "left": {"field": "amount"}, "right": {"source": "gl", "field": "balance", "where": "account == '1000'"}},
        {"id": "suspense", "left": {"field": "amount", "where": "amount > 1000"},
         "right": {"source": "gl", "field": "balance", "where": "account == '2000'"}, "message": "suspense not cleared"}]}, st)
    new = out["items"][2:]
    assert [(n["check"], n["difference"], n["message"]) for n in new] == [("suspense", -7.0, "suspense not cleared")]


async def test_sample_is_reproducible_and_keeps_the_rest_marked(lab):
    items = [{"item_id": f"i{n}", "amount": n * 10, "desk": "A" if n % 2 else "B"} for n in range(1, 21)]
    one = await lab.run("sample", {"method": "random", "size": 4, "always_include_when": "amount >= 200"}, lab.state(items))
    lab.excluded.clear()
    two = await lab.run("sample", {"method": "random", "size": 4, "always_include_when": "amount >= 200"}, lab.state(items))
    assert [i["item_id"] for i in one["items"]] == [i["item_id"] for i in two["items"]]
    assert len(one["items"]) == 5 and next(i for i in one["items"] if i["item_id"] == "i20")["sampled"] == "always"
    assert len(lab.excluded) == 15 and all(e["excluded_reason"] == "not in the sample" for e in lab.excluded)
    top = await lab.run("sample", {"method": "top", "size": 2, "field": "amount"}, lab.state(items))
    assert {i["item_id"] for i in top["items"]} == {"i20", "i19"}


async def test_score_adds_weights_reasons_and_a_band(lab):
    out = await lab.run("score", {"factors": [{"when": "amount > 100", "weight": 40, "label": "large"},
                                              {"when": "country in ['IR', 'KP']", "weight": 50, "label": "high-risk country"}],
                                  "bands": [{"label": "low", "upto": 30}, {"label": "medium", "upto": 60}, {"label": "high"}]},
                        lab.state([{"item_id": "a", "amount": 500, "country": "IR"}, {"item_id": "b", "amount": 5, "country": "GB"}]))
    a, b = out["items"]
    assert (a["score"], a["score_reasons"], a["band"]) == (90, ["large", "high-risk country"], "high")
    assert (b["score"], b["band"]) == (0, "low")


# ---------- phase 5: acquisition

async def test_match_n_keeps_only_what_does_not_agree_across_systems(lab):
    lab.tools.update({
        "procurement.purchase_orders": {"rows": [{"po": "P1", "amount": 100}, {"po": "P2", "amount": 50}, {"po": "P3", "amount": 10}]},
        "procurement.goods_receipts": {"rows": [{"po": "P1", "amount": 60}, {"po": "P1", "amount": 40}, {"po": "P2", "amount": 50}]},
        "procurement.invoices": {"rows": [{"po": "P1", "amount": 100}, {"po": "P2", "amount": 55}, {"po": "P3", "amount": 10}]}})
    out = await lab.run("match_n", {"keys": ["po"], "sources": [
        {"label": "po", "tool": "procurement.purchase_orders"}, {"label": "grn", "tool": "procurement.goods_receipts"},
        {"label": "inv", "tool": "procurement.invoices"}]}, lab.state([]))
    got = {i["po"]: i for i in out["items"]}
    assert set(got) == {"P2", "P3"}                                   # P1 agrees once receipts are summed
    assert (got["P2"]["break_type"], got["P2"]["difference"]) == ("amount_break", 5.0)
    assert got["P3"]["break_type"] == "missing_grn" and got["P3"]["grn_amount"] is None


async def test_intake_maps_columns_and_keeps_bad_rows_aside(lab):
    lab.tools["documents.read_workbook"] = {"rows": [
        {"Ref": "T1", "Amount": "1,250.50", "Ccy": "GBP"}, {"Ref": "T2", "Amount": "abc", "Ccy": "GBP"},
        {"Ref": "", "Amount": "3", "Ccy": "EUR"}]}
    out = await lab.run("intake", {"tool": "documents.read_workbook", "id_field": "ref", "required": ["ref"],
                                   "numbers": ["amount"], "columns": {"ref": "Ref", "amount": "Amount", "currency": "Ccy"}},
                        lab.state([]))
    assert out["items"] == [{"ref": "T1", "amount": 1250.5, "currency": "GBP", "source_row": 1, "item_id": "T1"}]
    assert sorted(e["intake_problems"][0] for e in lab.excluded) == ["amount is not a number ('abc')", "ref is missing"]


DOC = "Facility agreement\nBorrower: Kestrel SA\nMargin: 2.25%\nMaturity date: 2031-06-30\n"


async def test_extract_takes_only_values_found_in_the_document(lab):
    lab.tools["documents.read_pdf"] = {"rows": [{"text": DOC}]}
    cfg = {"tool": "documents.read_pdf", "accept_confidence": 0.7, "fields": [
        {"name": "margin", "pattern": r"Margin:\s*([\d.]+%)"}, {"name": "borrower"},
        {"name": "maturity_date", "hint": "Maturity date"}, {"name": "governing_law", "required": True}]}
    item = (await lab.run("extract", cfg, lab.state([])))["items"][-1]
    assert (item["margin"], item["borrower"], item["maturity_date"]) == ("2.25%", "Kestrel SA", "2031-06-30")
    assert item["governing_law"] is None
    assert item["extract_review"] == [{"field": "governing_law", "why": "not found", "quote": None}]

    strict = (await lab.run("extract", {**cfg, "accept_confidence": 0.9}, lab.state([])))["items"][-1]
    assert {r["field"] for r in strict["extract_review"]} == {"borrower", "maturity_date", "governing_law"}  # stub is 0.8 sure

    regulated = (await lab.run("extract", {**cfg, "regulated": True}, lab.state([])))["items"][-1]
    assert {r["field"] for r in regulated["extract_review"]} == {"margin", "borrower", "maturity_date", "governing_law"}
    assert regulated["extract_ok"] is False


async def test_extract_refuses_a_value_the_document_does_not_contain(lab, monkeypatch):
    from agent_one_finance import llm as llm_mod
    lab.tools["documents.read_pdf"] = {"rows": [{"text": DOC}]}

    class Inventive(llm_mod.StubLlm):
        async def extract(self, request):
            return {"borrower": {"value": "Acme Ltd", "quote": "Borrower: Kestrel SA", "confidence": 0.99}}

    monkeypatch.setattr(llm_mod, "llm", lambda: Inventive())
    item = (await lab.run("extract", {"tool": "documents.read_pdf", "fields": [{"name": "borrower"}]}, lab.state([])))["items"][-1]
    assert item["borrower"] is None and item["extract_review"][0]["why"] == "not in the document"


# ---------- phase 6: parties

async def test_screen_marks_candidates_only(lab):
    st = lab.state([{"item_id": "a", "client": "Blue Harbor Pte"}, {"item_id": "b", "client": "J. Patel"}],
                   datasets={"watch": [{"id": "W1", "name": "Blue Harbour Pte Ltd"}]})
    a, b = (await lab.run("screen", {"list": "watch", "fields": ["client"], "threshold": 0.8}, st))["items"]
    assert a["screen_candidate"] and a["screen_candidates"][0]["list_id"] == "W1"
    assert b["screen_candidate"] is False and b["screen_candidates"] == []


# ---------- what the platform checks

def _with(steps, settings, pause=None, **more):
    d = BASE.model_dump(by_alias=True)
    d["steps"], d["step_settings"] = steps, {**d["step_settings"], **settings}
    d["pause_before"] = pause if pause is not None else d.get("pause_before", [])
    d.update(more)
    return Manifest.model_validate(d)


def test_ordering_rules_for_write_back_waiting_and_people():
    base = [s for s in BASE.steps]
    post = {"post": {"type": "post", "with": {"tool": "payments.message_trail", "approver_roles": ["X"]}}}
    # a write-back step must come after record and the run must pause before it
    found = problems(_with([*base, "post"], post))
    assert "the run must pause before `post` for a second approval" in found
    found = problems(_with([*base[:-1], "post", base[-1]], post, pause=["post"]))
    assert any("after `record`" in p or "must come right after" in p for p in found)
    # an attestation needs a person at the tollgate before it
    att = {"att": {"type": "attest", "with": {"statement": "s", "roles": ["X"]}}}
    found = problems(_with([*base[:-2], "att", *base[-2:]], att))
    assert "pause_before: `att` needs a person first — add it to pause_before (its tollgate)" in found
    # a spawn needs a later await for its children
    spawn = {"kids": {"type": "spawn", "with": {"capability": "payments.exceptions", "key": {"entity": "$case.entity"}}}}
    found = problems(_with([*base[:-3], "kids", *base[-3:]], spawn))
    assert any("kids" in p and "children" in p for p in found)


def test_only_write_back_and_report_may_follow_record():
    assert any("only write-back and report" in p for p in
               order_problems(["load", "group", "reason", "draft", "validate", "review", "record", "flux"],
                              [], {"flux": "flux"},
                              {"flux": steps_v2.FluxCfg(history="h", key="k", value="v")}))


def test_a_reserved_outcome_the_model_proposed_is_withheld_for_a_person():
    from agent_one_finance import authority
    d = BASE.model_dump(by_alias=True)
    d["boundaries"] = [{"verdicts": ["RETURN"], "roles": ["PAYMENTS_LEAD"], "reason": "returning funds"}]
    m = Manifest.model_validate(d)
    g = {"group_key": {"reason_code": "AC04"}, "total": 10, "count": 1}
    by_model = authority.apply(m, g, {"verdict": "RETURN", "status": "proposed", "decided_by": "llm:x"})
    assert (by_model["status"], by_model["verdict"], by_model["withheld_proposal"]) == ("escalated", None, "RETURN")
    assert by_model["reason"] == "RESERVED: returning funds"
    by_rule = authority.apply(m, g, {"verdict": "RETURN", "status": "proposed", "decided_by": "rule"})
    assert by_rule["status"] == "proposed" and by_rule["reserved"]["roles"] == ["PAYMENTS_LEAD"]
    assert authority.apply(m, g, {"verdict": "REPAIR", "status": "proposed"}).get("reserved") is None
