"""Algorithm steps on their own: each adds evidence to the items, decides
nothing, and gives the same answer every time."""

import math
import random

import pytest

from agent_one_finance import algorithms, stepkit, steps_v2
from agent_one_finance.capabilities import seed_files

BASE = next(m for m in seed_files() if m.id == "payments.exceptions")


@pytest.fixture
def lab(monkeypatch):
    saved, datasets, calls, tools = [], {}, [], {}

    async def save(state, items):
        saved.append(items)

    async def keep(state, step_id, name, source, rows):
        datasets[name] = rows

    async def exclude(state, step_id, items, reason):
        pass

    async def call(state, step_id, tool, args, *, write_by=None):
        calls.append((tool, args))
        return tools[tool](args) if callable(tools[tool]) else tools[tool]

    for mod in (steps_v2, algorithms):
        monkeypatch.setattr(mod, "_save", save)
        monkeypatch.setattr(mod, "_keep_dataset", keep)
    monkeypatch.setattr(steps_v2, "_call", call)
    monkeypatch.setattr(steps_v2, "_exclude", exclude)

    class Lab:
        def state(self, items, **extra):
            return {"case_id": "lab-1", "case_key": {"book": "PRIME-MB-11", "cob": "2026-10-06"},
                    "manifest": BASE.model_dump(by_alias=True), "items": items, **extra}

        async def run(self, type_name, cfg, state, step_id="step"):
            t = stepkit.TYPES[type_name]
            return await t.run(state, t.config.model_validate(cfg), step_id)

    lab = Lab()
    lab.datasets, lab.calls, lab.tools = datasets, calls, tools
    return lab


def by_id(out):
    return {i["item_id"]: i for i in out["items"]}


# ---------- offsets

async def test_offsets_pair_equal_and_opposite_in_the_same_book_only(lab):
    items = [{"item_id": "GILT 5Y", "book": "B1", "difference": 42000.0},
             {"item_id": "UST 2Y", "book": "B1", "difference": -42000.005},
             {"item_id": "JGB 10Y", "book": "B2", "difference": -42000.0},     # another book: never paired
             {"item_id": "BUND", "book": "B1", "difference": 500.0}]
    out = await lab.run("offsets", {"amount": "difference", "within": ["book"], "tolerance": 0.01}, lab.state(items))
    i = by_id(out)
    assert i["GILT 5Y"]["offset"] and i["GILT 5Y"]["offset_with"] == "UST 2Y"
    assert i["UST 2Y"]["offset_with"] == "GILT 5Y" and i["UST 2Y"]["offset_pair"] == i["GILT 5Y"]["offset_pair"]
    assert not i["JGB 10Y"]["offset"] and not i["BUND"]["offset"]
    assert [x["item_id"] for x in out["items"]] == [x["item_id"] for x in items]       # order kept
    assert lab.datasets["offset"] == [{"pair": "OFFSET-1", "positive": "GILT 5Y", "negative": "UST 2Y",
                                       "amount": 42000.0, "difference": -0.0, "book": "B1"}]


async def test_offsets_pair_each_item_once_and_the_closest_first(lab):
    items = [{"item_id": "a", "amount": 100.0}, {"item_id": "b", "amount": -100.0},
             {"item_id": "c", "amount": -99.995}, {"item_id": "d", "amount": 100.0}]
    i = by_id(await lab.run("offsets", {"tolerance": 0.01}, lab.state(items)))
    assert (i["a"]["offset_with"], i["d"]["offset_with"]) == ("b", "c")
    again = by_id(await lab.run("offsets", {"tolerance": 0.01}, lab.state(list(reversed(items)))))
    assert again["a"]["offset_with"] == "b"                                            # reproducible


# ---------- subset_match

def test_find_subsets_smallest_first_and_says_if_another_works():
    idx, count, done = algorithms.find_subsets(100.0, [60.0, 30.0, 40.0, 10.0], max_size=3, tolerance=0.01)
    assert sorted(idx) == [0, 2] and count == 1 and done                    # 60 + 40
    idx, count, _ = algorithms.find_subsets(70.0, [60.0, 10.0, 30.0, 40.0], max_size=3, tolerance=0.01)
    assert count == 2                                                       # 60+10 and 30+40: ambiguous
    assert algorithms.find_subsets(5.0, [1.0, 1.0], max_size=2, tolerance=0.01)[0] is None


def test_find_subsets_stops_at_its_limit_and_says_so():
    vals = [float(random.Random(1).randint(1, 10**6)) for _ in range(30)]
    _, _, done = algorithms.find_subsets(-1.0, vals, max_size=5, tolerance=0.0, limit=1000)
    assert done is False


async def test_subset_match_explains_a_split_booking_from_a_data_set(lab):
    events = [{"event": "partial booking", "ref": "E1", "book": "B1", "amount": 25000.0},
              {"event": "partial booking", "ref": "E2", "book": "B1", "amount": 17000.0},
              {"event": "late booking", "ref": "E3", "book": "B1", "amount": 3000.0},
              {"event": "partial booking", "ref": "E9", "book": "B2", "amount": 17000.0}]
    st = lab.state([{"item_id": "UST 10Y", "book": "B1", "difference": 42000.0},
                    {"item_id": "BUND", "book": "B1", "difference": 999.0}], datasets={"events": events})
    i = by_id(await lab.run("subset_match", {"target": "difference", "pool": "events", "pool_value": "amount",
                                             "pool_label": "ref", "within": ["book"], "as": "split"}, st))
    assert i["UST 10Y"]["split_found"] and i["UST 10Y"]["split_unique"]
    assert sorted(m["label"] for m in i["UST 10Y"]["split_members"]) == ["E1", "E2"] and i["UST 10Y"]["split_sum"] == 42000.0
    assert not i["BUND"]["split_found"] and i["BUND"]["split_members"] == []


async def test_subset_match_among_items_finds_breaks_that_net_to_zero(lab):
    items = [{"item_id": "a", "amount": 300.0}, {"item_id": "b", "amount": -100.0},
             {"item_id": "c", "amount": -200.0}, {"item_id": "d", "amount": 7.0}]
    i = by_id(await lab.run("subset_match", {"sign": "opposite", "when": "amount > 0"}, lab.state(items)))
    assert sorted(m["label"] for m in i["a"]["subset_members"]) == ["b", "c"]
    assert not i["b"]["subset_found"]                                                   # `when` limits who is searched


def test_subset_match_names_its_pool_data_set_for_the_order_check():
    t = stepkit.TYPES["subset_match"]
    cfg = t.config.model_validate({"pool": "events"})
    assert "dataset:events" in t.needs(cfg) and t.dataset_refs(cfg) == {"events"}


# ---------- trend

def test_describe_trend_reads_the_shape():
    assert algorithms.describe_trend([100, 200, 400], 3)["direction"] == "growing"
    assert algorithms.describe_trend([400, 200, 100], 3)["direction"] == "shrinking"
    assert algorithms.describe_trend([100, -100, 100, -100], 3)["direction"] == "flipping"
    t = algorithms.describe_trend([10, 20, 30], 3)
    assert t["slope"] == 10.0 and t["growing"]
    assert algorithms.describe_trend([5, 6], 3)["direction"] is None                    # too short: not judged


async def test_trend_orders_cobs_ago_oldest_first_then_today(lab):
    history = [{"instrument": "X", "cobs_ago": n, "difference": v} for n, v in ((1, 300.0), (2, 200.0), (3, 100.0))]
    st = lab.state([{"item_id": "X", "instrument": "X", "difference": 400.0},
                    {"item_id": "Y", "instrument": "Y", "difference": 5.0}], datasets={"history": history})
    i = by_id(await lab.run("trend", {"history": "history", "key": "instrument", "value": "difference",
                                      "history_value": "difference", "order": "cobs_ago"}, st))
    assert i["X"]["trend_direction"] == "growing" and i["X"]["trend_points"] == 4 and i["X"]["trend_slope"] == 100.0
    assert i["Y"]["trend_direction"] is None and i["Y"]["trend_points"] == 1


# ---------- cluster

async def test_cluster_counts_other_books_breaking_the_same_way(lab):
    lab.tools["mbrec.breaks_all"] = {"rows": [
        {"book": "B2", "instrument": "GILT 5Y", "difference": -40000.0},
        {"book": "B3", "instrument": "GILT 5Y", "difference": -45000.0},
        {"book": "B4", "instrument": "GILT 5Y", "difference": 41000.0},       # opposite sign: not the same break
        {"book": "B5", "instrument": "UST 2Y", "difference": -40000.0},
        {"book": "B1", "instrument": "GILT 5Y", "difference": -42000.0}]}     # its own book: not counted
    st = lab.state([{"item_id": "GILT 5Y", "book": "B1", "instrument": "GILT 5Y", "difference": -42000.0},
                    {"item_id": "UST 2Y", "book": "B1", "instrument": "UST 2Y", "difference": -42000.0}])
    i = by_id(await lab.run("cluster", {"same": ["instrument"], "across": "book", "amount": "difference",
                                        "peers_tool": "mbrec.breaks_all", "peers_args": {"cob": "$case.cob"}}, st))
    assert lab.calls == [("mbrec.breaks_all", {"cob": "2026-10-06"})]
    assert i["GILT 5Y"]["systemic"] and i["GILT 5Y"]["systemic_count"] == 3
    assert "systemic_where" not in i["GILT 5Y"]                                        # other books stay unnamed
    assert not i["UST 2Y"]["systemic"] and i["UST 2Y"]["systemic_count"] == 2


# ---------- fuzzy_match

def test_jaro_winkler_known_values():
    assert math.isclose(algorithms.jaro_winkler("MARTHA", "MARHTA"), 0.9611, abs_tol=1e-4)
    assert math.isclose(algorithms.jaro_winkler("DIXON", "DICKSONX"), 0.8133, abs_tol=1e-4)
    assert algorithms.jaro_winkler("ABC", "ABC") == 1.0 and algorithms.jaro_winkler("", "A") == 0.0


async def test_fuzzy_match_finds_a_reference_typo_with_a_similar_amount(lab):
    bo = [{"instrument": "IRS5Y USD", "mtm": 135000.0}, {"instrument": "IRS 5Y EUR", "mtm": 9.0},
          {"instrument": "GILT 5Y", "mtm": 1.0}]
    st = lab.state([{"item_id": "IRS 5Y USD", "instrument": "IRS 5Y USD", "break_type": "missing_motif", "cats_amount": 135720.18},
                    {"item_id": "GILT 5Y", "instrument": "GILT 5Y", "break_type": "amount_break", "cats_amount": 1.0}],
                   datasets={"bo": bo})
    i = by_id(await lab.run("fuzzy_match", {"field": "instrument", "pool": "bo", "when": "break_type == 'missing_motif'",
                                            "amount": "cats_amount", "pool_amount": "mtm", "amount_within_pct": 2}, st))
    assert i["IRS 5Y USD"]["near"] and [c["reference"] for c in i["IRS 5Y USD"]["near_candidates"]] == ["IRS5Y USD"]
    assert not i["GILT 5Y"]["near"]                                                    # not searched, and an exact name is no near match


# ---------- benford

def test_benford_conforms_on_benford_data_and_not_on_flat_data():
    rng = random.Random(7)
    ben = [10 ** rng.uniform(0, 6) for _ in range(5000)]
    flat = [rng.uniform(100, 999) for _ in range(5000)]
    assert algorithms.benford_test(ben)["conformity"] in ("close conformity", "acceptable conformity")
    assert algorithms.benford_test(flat)["conformity"] == "nonconformity"


async def test_benford_is_not_run_on_too_few_and_flags_round_amounts(lab):
    st = lab.state([{"item_id": str(n), "amount": v} for n, v in enumerate([5000.0, 123.4, 18.0])])
    out = await lab.run("benford", {"field": "amount", "min_items": 100}, st)
    i = by_id(out)
    assert i["0"]["round_amount"] and not i["1"]["round_amount"]
    assert lab.datasets["benford"][0]["status"].startswith("not run") and not any(x["benford_over"] for x in out["items"])


# ---------- robust and seasonal history, MUS, score formula

async def test_robust_anomaly_is_not_hidden_by_an_outlier_in_the_history(lab):
    hist = [{"account": "A", "value": v} for v in (100, 101, 99, 100, 102, 98, 5000)]
    st = lab.state([{"item_id": "x", "account": "A", "amount": 130}], datasets={"h": hist})
    base = {"history": "h", "key": "account", "value": "amount", "threshold": 3.5}
    plain = by_id(await lab.run("anomaly", base, st))["x"]
    robust = by_id(await lab.run("anomaly", {**base, "method": "robust"}, st))["x"]
    assert not plain["anomaly"] and robust["anomaly"]                                 # the 5000 inflated the plain spread


async def test_seasonal_history_compares_month_end_with_month_end(lab):
    hist = [{"account": "A", "value": 100, "month_end": False}, {"account": "A", "value": 110, "month_end": False},
            {"account": "A", "value": 1000, "month_end": True}, {"account": "A", "value": 1100, "month_end": True}]
    st = lab.state([{"item_id": "x", "account": "A", "amount": 1050, "month_end": True}], datasets={"h": hist})
    x = by_id(await lab.run("flux", {"history": "h", "key": "account", "value": "amount", "same": "month_end"}, st))["x"]
    assert x["flux_baseline"] == 1050.0 and x["flux_change"] == 0.0


async def test_mus_takes_every_interval_and_always_the_big_items(lab):
    items = [{"item_id": f"i{n:02d}", "amount": 10.0} for n in range(20)] + [{"item_id": "big", "amount": 500.0}]
    st = lab.state(items)
    out = await lab.run("sample", {"method": "mus", "field": "amount", "size": 5}, st)
    picked = {i["item_id"] for i in out["items"]}
    assert "big" in picked and len(picked) < 5            # the big item takes several of the 5 points (interval 140)
    even = await lab.run("sample", {"method": "mus", "field": "amount", "size": 5}, lab.state(items[:20]))
    assert len(even["items"]) == 5                       # equal items: one per interval
    again = await lab.run("sample", {"method": "mus", "field": "amount", "size": 5}, st)
    assert {i["item_id"] for i in again["items"]} == picked                            # same case, same sample


async def test_score_formula_makes_a_priority_with_its_reasons(lab):
    st = lab.state([{"item_id": "a", "difference": -50000, "age_days": 2, "recurring": True},
                    {"item_id": "b", "difference": 1000, "age_days": 0, "recurring": False}])
    i = by_id(await lab.run("score", {"formula": "abs(difference) / 10000 + age_days * 5 + ifelse(recurring, 20, 0)",
                                      "as": "priority", "bands": [{"label": "low", "upto": 10}, {"label": "high"}]}, st))
    assert (i["a"]["priority"], i["a"]["band"]) == (35.0, "high") and (i["b"]["priority"], i["b"]["band"]) == (0.1, "low")
    with pytest.raises(ValueError):
        stepkit.TYPES["score"].config.model_validate({})


# ---------- proposed checks from approved decisions

def _ex(n, row, label, scope=("fobo-prime", "K")):
    return [{"scope": scope, "row": dict(row), "label": label, "case": f"{label}-{i}"} for i in range(n)]


def test_proposed_checks_find_the_condition_that_predicts_the_verdict():
    from agent_one_finance import rules
    from agent_one_finance.insights import propose_checks
    ex = (_ex(6, {"age_days": 2, "trend_direction": "growing", "systemic": False}, "ESCALATE")
          + _ex(5, {"age_days": 2, "trend_direction": "shrinking", "systemic": False}, "MONITOR"))
    got = {p["verdict"]: p for p in propose_checks(ex, needed=5)}
    assert got["ESCALATE"]["when"] == "trend_direction == 'growing'" and got["ESCALATE"]["covers"] == 6
    assert got["MONITOR"]["precision"] == 1.0 and got["MONITOR"]["wrong"] == 0
    for p in got.values():                                         # each proposal is a valid playbook expression
        rules.compile_expr(p["when"])


def test_proposed_checks_need_enough_cases_and_more_than_one_verdict():
    from agent_one_finance.insights import propose_checks
    assert propose_checks(_ex(9, {"age_days": 3}, "ESCALATE"), needed=5) == []      # one verdict: nothing to learn
    few = _ex(3, {"flag": True}, "POST") + _ex(6, {"flag": False}, "ESCALATE")
    assert [p["verdict"] for p in propose_checks(few, needed=5)] == ["ESCALATE"]    # POST has only 3 cases


def test_proposed_checks_join_two_conditions_when_one_is_not_enough():
    from agent_one_finance.insights import propose_checks
    ex = (_ex(5, {"big": True, "aged": True}, "ESCALATE") + _ex(5, {"big": True, "aged": False}, "POST")
          + _ex(5, {"big": False, "aged": True}, "POST"))
    p = next(p for p in propose_checks(ex, needed=5) if p["verdict"] == "ESCALATE")
    assert p["when"] in ("aged and big", "big and aged") and p["wrong"] == 0
