"""The workflow can be reconfigured, but not into something unsafe."""

import copy

import pytest
import yaml
from pydantic import ValidationError

from app.workflow.config import DEFAULT_PATH, WorkflowConfig, read_workflow
from app.workflow.graph import build_graph
from app.workflow.registry import REQUIRED_STEPS, STEPS


def _raw():
    return yaml.safe_load(DEFAULT_PATH.read_text())


def _cfg(mutate=None):
    raw = copy.deepcopy(_raw())
    if mutate:
        mutate(raw)
    return WorkflowConfig.model_validate(raw)


def _refused(mutate) -> str:
    with pytest.raises((ValidationError, ValueError)) as exc:
        _cfg(mutate)
    return str(exc.value)


def _move(step, to):
    def f(r):
        r["steps"].remove(step)
        r["steps"].insert(to, step)
    return f


def test_the_checked_in_workflow_is_valid():
    wf = read_workflow()
    assert wf.steps[0] == "resolve" and wf.steps[-1] == "record"
    assert "review" in wf.pause_before


def test_every_configured_step_is_registered():
    assert set(read_workflow().steps) <= set(STEPS)


# --- refused -------------------------------------------------------------

def test_record_cannot_run_before_review():
    """That would record a decision nobody made."""
    msg = _refused(_move("record", 7))
    assert "'record'" in msg


def test_the_playbook_step_cannot_be_removed():
    msg = _refused(lambda r: r["steps"].remove("reason"))
    assert "'reason' cannot be removed" in msg
    assert "guards" in msg


def test_the_grounding_check_cannot_be_removed():
    assert "'validate' cannot be removed" in _refused(lambda r: r["steps"].remove("validate"))


def test_human_sign_off_cannot_be_removed():
    assert "'review'" in _refused(lambda r: r["steps"].remove("review"))


def test_the_pause_for_a_person_cannot_be_removed():
    assert "must include 'review'" in _refused(lambda r: r.update(pause_before=[]))


def test_a_step_cannot_run_before_the_step_it_depends_on():
    msg = _refused(_move("draft", 2))
    assert "'draft' needs 'pattern_groups'" in msg
    assert "produced by group" in msg


def test_an_unknown_step_is_refused_and_the_known_ones_listed():
    msg = _refused(lambda r: r["steps"].__setitem__(1, "gathr"))
    assert "'gathr' is not a known step" in msg
    assert "gather" in msg


def test_a_duplicated_step_is_refused():
    assert "more than once" in _refused(lambda r: r["steps"].append("rank"))


def test_an_unknown_reasoner_is_refused():
    assert "not one of" in _refused(
        lambda r: r["settings"]["reason"].update(reasoner="gpt"))


def test_a_misspelt_setting_is_refused_not_ignored():
    """A typo must not silently leave the default in force."""
    assert "prior_lookback_days" in _refused(
        lambda r: r["settings"]["gather"].update(prior_lookback_days=90))


def test_lineage_depth_is_capped_at_the_recursion_ceiling():
    _refused(lambda r: r["settings"]["gather"].update(lineage_max_depth=9))


def test_every_required_step_states_why():
    for name in REQUIRED_STEPS:
        assert STEPS[name].required_because


# --- allowed -------------------------------------------------------------

def test_the_optional_rank_step_can_be_dropped():
    wf = _cfg(lambda r: r["steps"].remove("rank"))
    assert "rank" not in wf.steps


def test_a_second_pause_can_be_added():
    wf = _cfg(lambda r: r.update(pause_before=["reason", "review"]))
    assert wf.pause_before == ["reason", "review"]


def test_settings_can_be_changed():
    wf = _cfg(lambda r: r["settings"]["gather"].update(priors_lookback_days=30))
    assert wf.settings.gather.priors_lookback_days == 30


# --- the config drives the graph -----------------------------------------

def test_the_graph_is_built_from_the_configured_steps():
    wf = _cfg(lambda r: r["steps"].remove("rank"))
    g = build_graph(checkpointer=None, config=wf)
    assert "rank" not in g.nodes
    assert {"resolve", "reason", "review", "record"} <= set(g.nodes)


def test_the_graph_pauses_where_the_config_says():
    wf = _cfg(lambda r: r.update(pause_before=["reason", "review"]))
    g = build_graph(checkpointer=None, config=wf)
    assert set(g.interrupt_before_nodes) == {"reason", "review"}
