"""The compiled graph and its decision logic, as the Workflow tab consumes it.

Every assertion here checks the view against the code it claims to describe
(the registry, the node source files, determinism.py, guards.py, the
playbook) rather than against a hand-typed expectation, so this test cannot
pass while the view has drifted from what actually runs.
"""

import copy
import inspect
import json
import re

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from app.playbook.loader import read_playbook
from app.reasoning import determinism, guards
from app.workflow import registry
from app.workflow.config import dump_config, read_workflow
from app.workflow.graph_view import defined_in, graph_view
from app.workflow.nodes.escalate import REASONS, escalate

ESCALATION_RE = re.compile(r'"escalation_reason":\s*"([A-Z_]+)"')


def _cfg(*edits):
    raw = dump_config(read_workflow())
    for edit in edits:
        edit(raw)
    from app.workflow.config import WorkflowConfig
    return WorkflowConfig.model_validate(raw)


def _view(*edits, number=1) -> dict:
    return graph_view(_cfg(*edits), number)


# --- nodes -------------------------------------------------------------

def test_nodes_are_start_steps_escalate_end_in_relative_order():
    ids = [n["id"] for n in _view()["nodes"]]
    steps = read_workflow().steps
    assert ids[0] == "__start__"
    assert ids[1:1 + len(steps)] == steps
    assert ids[-2] == "escalate"
    assert ids[-1] == "__end__"


def test_only_review_is_paused_before():
    paused = {n["id"] for n in _view()["nodes"] if n["paused_before"]}
    assert paused == {"review"}


def test_step_nodes_carry_decided_by_and_others_do_not():
    by_id = {n["id"]: n for n in _view()["nodes"]}
    assert by_id["resolve"]["decided_by"] == "code"
    assert by_id["reason"]["decided_by"] == "playbook+reasoner"
    for special in ("__start__", "__end__", "escalate"):
        assert "decided_by" not in by_id[special]


def test_node_kinds_and_labels():
    by_id = {n["id"]: n for n in _view()["nodes"]}
    assert by_id["__start__"] == {"id": "__start__", "kind": "start", "label": "Start",
                                   "paused_before": False}
    assert by_id["__end__"] == {"id": "__end__", "kind": "end", "label": "End",
                                 "paused_before": False}
    assert by_id["escalate"]["kind"] == "escalate"
    assert by_id["escalate"]["label"] == "Escalate"
    assert by_id["resolve"]["kind"] == "step"
    assert by_id["resolve"]["label"] == registry.STEPS["resolve"].label


# --- edges ---------------------------------------------------------------

def _edges_by_pair(view):
    return {(e["source"], e["target"]): e for e in view["edges"]}


def test_resolve_and_gather_escalate_edges_are_conditional_with_reasons():
    edges = _edges_by_pair(_view())
    e = edges[("resolve", "escalate")]
    assert e["conditional"] is True
    assert e["label"] == "if escalated"
    assert e["reasons"] == ["UNRESOLVED_BOOK", "AMBIGUOUS_BOOK"]

    e = edges[("gather", "escalate")]
    assert e["conditional"] is True
    assert e["label"] == "if escalated"
    assert e["reasons"] == ["DELTA_UNAVAILABLE", "CHECKS_UNAVAILABLE"]


def test_resolve_and_gather_otherwise_edges_are_conditional():
    edges = _edges_by_pair(_view())
    assert edges[("resolve", "gather")]["conditional"] is True
    assert edges[("resolve", "gather")]["label"] == "otherwise"
    assert "reasons" not in edges[("resolve", "gather")]

    assert edges[("gather", "group")]["conditional"] is True
    assert edges[("gather", "group")]["label"] == "otherwise"


def test_group_to_reason_is_unconditional():
    e = _edges_by_pair(_view())[("group", "reason")]
    assert e == {"source": "group", "target": "reason", "conditional": False, "label": None}


def test_terminal_edges_exist():
    edges = _edges_by_pair(_view())
    assert ("record", "__end__") in edges
    assert ("escalate", "__end__") in edges
    assert edges[("record", "__end__")]["conditional"] is False
    assert edges[("escalate", "__end__")]["conditional"] is False


def test_dropping_rank_removes_its_node_and_links_reason_to_draft():
    view = _view(lambda r: r["steps"].remove("rank"))
    ids = [n["id"] for n in view["nodes"]]
    assert "rank" not in ids
    e = _edges_by_pair(view)[("reason", "draft")]
    assert e["conditional"] is False and e["label"] is None


# --- registry: escalates_when does not drift from the code ---------------

def test_every_escalates_when_code_is_a_known_reason():
    for step in registry.STEPS.values():
        for code, _when in step.escalates_when:
            assert code in REASONS


def test_every_can_escalate_step_has_at_least_one_escalates_when():
    for step in registry.STEPS.values():
        if step.can_escalate:
            assert step.escalates_when


def test_escalation_reasons_in_node_source_match_the_registry_exactly():
    """No code can appear in escalates_when without being raised in the node,
    and no code raised in the node can be missing from escalates_when."""
    for step in registry.STEPS.values():
        if not step.escalates_when:
            continue
        source = inspect.getsource(inspect.getmodule(step.fn))
        in_source = set(ESCALATION_RE.findall(source))
        in_registry = {code for code, _when in step.escalates_when}
        assert in_source == in_registry, step.name


def test_catalogue_carries_escalates_when():
    by_name = {s["name"]: s for s in registry.catalogue()}
    assert by_name["resolve"]["escalates_when"] == [
        {"code": "UNRESOLVED_BOOK", "when": "no book matches"},
        {"code": "AMBIGUOUS_BOOK", "when": "more than one matches; never auto-picked"},
    ]
    assert by_name["group"]["escalates_when"] == []
    json.dumps(by_name)


# --- determinism.py / guards.py: ordered lists next to the code ----------

def test_pattern_order_covers_exactly_the_pattern_constants():
    constants = {
        v for k, v in vars(determinism).items()
        if k.startswith("PATTERN_") and isinstance(v, str)
    }
    assert {code for code, _meaning, _verdict in determinism.PATTERN_ORDER} == constants
    assert [code for code, _meaning, _verdict in determinism.PATTERN_ORDER] == [
        "posting_failure", "missing_side", "missing_price",
        "side_double", "reapplication", "single_cause",
    ]


def test_guard_rules_ids_in_application_order():
    assert [rid for rid, _rule in guards.GUARD_RULES] == ["§8", "R6", "R2", "none", "P1"]


@pytest.mark.parametrize("rule_id", ["§8", "R6", "R2", "P1"])
def test_guard_rule_ids_appear_in_guards_source(rule_id):
    assert rule_id in inspect.getsource(guards)


# --- defined_in ------------------------------------------------------------

def test_defined_in_points_at_the_node_source():
    from app.workflow.nodes.resolve import resolve
    assert defined_in(resolve).startswith("apps/api/app/workflow/nodes/resolve.py")


def test_defined_in_points_at_the_router():
    from app.workflow.graph import _router
    assert defined_in(_router).startswith("apps/api/app/workflow/graph.py")


def test_defined_in_falls_back_to_the_dotted_module_name_outside_repo_root():
    """Never an absolute filesystem path in front of a controller — an
    object defined outside REPO_ROOT (e.g. the stdlib, installed elsewhere
    on this machine) gets the module's dotted name instead."""
    import json
    result = defined_in(json.dumps)
    assert not result.startswith("/")
    assert result == "json · dumps"


def test_defined_in_is_used_throughout_the_view():
    view = _view()
    assert view["router"]["defined_in"].startswith("apps/api/app/workflow/graph.py")
    assert view["logic"]["resolve"]["defined_in"].startswith(
        "apps/api/app/workflow/nodes/resolve.py")
    assert view["logic"]["escalate"]["defined_in"].startswith(
        "apps/api/app/workflow/nodes/escalate.py")
    assert view["decision"]["defined_in"] == [
        defined_in(determinism.classify), defined_in(guards.guard_verdict),
    ]


# --- escalate panel: only reachable reason codes ----------------------------

def test_escalate_logic_lists_only_codes_configured_steps_actually_raise():
    """Only resolve (UNRESOLVED_BOOK, AMBIGUOUS_BOOK) and gather
    (DELTA_UNAVAILABLE, CHECKS_UNAVAILABLE) have a non-empty escalates_when
    in the registry; no configured step raises UNMAPPED_BOOK,
    RETRY_EXHAUSTED or VALIDATION_FAILED, so those must not be claimed as
    reachable by any step."""
    esc = _view()["logic"]["escalate"]
    assert esc["raised_by"] == [
        {"step": "resolve", "label": registry.STEPS["resolve"].label,
         "codes": ["UNRESOLVED_BOOK", "AMBIGUOUS_BOOK"]},
        {"step": "gather", "label": registry.STEPS["gather"].label,
         "codes": ["DELTA_UNAVAILABLE", "CHECKS_UNAVAILABLE"]},
    ]
    assert esc["other_known"] == ["RETRY_EXHAUSTED", "UNMAPPED_BOOK", "VALIDATION_FAILED"]
    # Every code accepted by escalate() appears exactly once, either raised
    # or in other_known — nothing invented, nothing dropped.
    raised = {c for group in esc["raised_by"] for c in group["codes"]}
    assert raised | set(esc["other_known"]) == REASONS
    assert not (raised & set(esc["other_known"]))


def test_escalate_logic_is_scoped_to_the_configured_steps():
    """resolve and gather are the only steps required_because non-removable
    (dropping either invalidates the config), but raised_by is still built
    from `cfg.steps`, not the whole registry — dropping an unrelated,
    removable step (rank, which cannot escalate) must not change it."""
    view = _view(lambda r: r["steps"].remove("rank"))
    esc = view["logic"]["escalate"]
    steps_with_codes = {g["step"] for g in esc["raised_by"]}
    assert steps_with_codes == {"resolve", "gather"}


# --- decision: patterns carry a verdict, cause checks say whether they settle --

def test_decision_patterns_carry_the_verdict_classify_actually_sets():
    view = _view()["decision"]
    by_code = {p["code"]: p["verdict"] for p in view["patterns"]}
    assert by_code["posting_failure"] == "CORRECT_AND_REPOST"
    assert by_code["missing_side"] is None
    assert by_code["missing_price"] == "DO_NOT_POST"
    assert by_code["side_double"] == "DO_NOT_POST"
    assert by_code["reapplication"] == "POST"
    assert by_code["single_cause"] == determinism.VERDICT_FROM_PLAYBOOK


def test_decision_cause_checks_carry_settles_matching_their_side():
    view = _view()["decision"]
    for row in view["cause_checks"]:
        assert row["settles"] == (row["side"] in ("FO", "BO"))
    settles_false = {r["check"] for r in view["cause_checks"] if not r["settles"]}
    assert settles_false == {"C3", "C4"}


def test_decision_lists_unresolved_when():
    view = _view()["decision"]
    assert view["unresolved_when"] == list(determinism.UNRESOLVED_WHEN)


# --- decision: matches the playbook exactly --------------------------------

def test_decision_cause_checks_and_default_verdicts_match_the_playbook():
    pb = read_playbook()
    view = _view()["decision"]

    expected_checks = [
        {"check": check, "category": c.category,
         "category_name": pb.categories[c.category].name,
         "side": c.side, "settles": c.side in ("FO", "BO"), "reason": c.reason}
        for check, c in sorted(pb.cause_checks.items())
    ]
    assert view["cause_checks"] == expected_checks

    expected_verdicts = [
        {"category": code, "category_name": pb.categories[code].name,
         "FO": by_side["FO"], "BO": by_side["BO"]}
        for code, by_side in sorted(pb.default_verdicts.items())
    ]
    assert view["default_verdicts"] == expected_verdicts

    assert view["reasoner"] == "none"
    assert view["guards"] == [{"id": rid, "rule": rule} for rid, rule in guards.GUARD_RULES]
    assert view["patterns"] == [
        {"code": code, "meaning": meaning, "verdict": verdict}
        for code, meaning, verdict in determinism.PATTERN_ORDER
    ]


def test_view_is_plain_json():
    json.dumps(_view())


# --- route -------------------------------------------------------------

@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    monkeypatch.delenv("FOBO_REASONER", raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                            base_url="http://test") as c:
        yield c


ASHA = {"X-Dev-Caller": "asha"}


async def _draft(client, config, *, note="drop rank", based_on=1):
    return await client.post("/api/workflow/drafts", headers={},
                              json={"config": config, "note": note, "based_on": based_on})


async def _approve(client, number, *, key="k1"):
    return await client.post(f"/api/workflow/versions/{number}/approve",
                              headers={"Idempotency-Key": key, **ASHA})


async def test_the_graph_route_serves_the_active_version(client):
    r = await client.get("/api/workflow/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert body["reasoner_override"] is None
    assert any(n["id"] == "rank" for n in body["nodes"])


async def test_an_approved_change_is_reflected_and_old_versions_still_show(client):
    raw = copy.deepcopy(dump_config(read_workflow()))
    raw["steps"].remove("rank")
    number = (await _draft(client, raw)).json()["number"]
    await _approve(client, number)

    active = (await client.get("/api/workflow/graph")).json()
    assert not any(n["id"] == "rank" for n in active["nodes"])

    v1 = (await client.get("/api/workflow/graph?version=1")).json()
    assert any(n["id"] == "rank" for n in v1["nodes"])


async def test_an_unknown_version_is_a_404(client):
    r = await client.get("/api/workflow/graph?version=99")
    assert r.status_code == 404


async def test_the_reasoner_override_is_reported(client, monkeypatch):
    monkeypatch.setenv("FOBO_REASONER", "direct")
    r = await client.get("/api/workflow/graph")
    assert r.json()["reasoner_override"] == "direct"
