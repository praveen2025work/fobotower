"""What the Workflow tab is told about each step and setting."""

import copy
import json

import pytest
import yaml
from pydantic import ValidationError

from app.workflow.config import (
    DEFAULT_PATH,
    WorkflowConfig,
    dump_config,
    errors_of,
    read_workflow,
    settings_schema,
)
from app.workflow.registry import DECIDED_BY, INITIAL_INPUTS, STEPS, catalogue


def _raw():
    return copy.deepcopy(yaml.safe_load(DEFAULT_PATH.read_text()))


def test_the_catalogue_describes_every_registered_step_in_registry_order():
    assert [s["name"] for s in catalogue()] == list(STEPS)


def test_each_step_says_who_decides_it():
    by = {s["name"]: s["decided_by"] for s in catalogue()}
    assert by == {
        "resolve": "code", "gather": "code", "group": "code",
        "reason": "playbook+reasoner", "rank": "code+model", "draft": "template",
        "validate": "code", "review": "human", "record": "code",
    }
    assert set(by.values()) <= set(DECIDED_BY)


def test_only_rank_is_removable():
    assert [s["name"] for s in catalogue() if s["removable"]] == ["rank"]


def test_every_locked_step_says_why():
    for s in catalogue():
        assert s["removable"] or s["required_because"]


def test_the_catalogue_is_plain_json():
    json.dumps(catalogue())


def test_only_resolve_and_gather_carry_escalates_when():
    by_name = {s["name"]: s["escalates_when"] for s in catalogue()}
    assert [n for n, v in by_name.items() if v] == ["resolve", "gather"]
    assert {c["code"] for c in by_name["resolve"]} == {"UNRESOLVED_BOOK", "AMBIGUOUS_BOOK"}
    assert {c["code"] for c in by_name["gather"]} == {"DELTA_UNAVAILABLE", "CHECKS_UNAVAILABLE"}
    for name in STEPS:
        if not STEPS[name].can_escalate:
            assert by_name[name] == []


def test_the_run_supplies_its_workflow_version():
    assert "workflow_version" in INITIAL_INPUTS


def test_dump_config_uses_yaml_names_and_order():
    d = dump_config(read_workflow())
    assert list(d) == ["version", "name", "steps", "pause_before", "settings"]
    assert "validate" in d["settings"] and "validate_" not in d["settings"]
    assert WorkflowConfig.model_validate(d) == read_workflow()


def test_the_settings_schema_carries_the_validators_bounds():
    schema = settings_schema()
    depth = schema["gather"]["lineage_max_depth"]
    assert (depth["type"], depth["min"], depth["max"], depth["default"]) == ("integer", 1, 4, 4)
    timeout = schema["session_service"]["timeout_seconds"]
    assert timeout["type"] == "number" and timeout["exclusive_min"] == 0


def test_the_reasoner_is_offered_as_a_choice():
    r = settings_schema()["reason"]["reasoner"]
    assert r["type"] == "enum" and r["options"] == ["none", "session_service", "direct"]


def test_policy_params_are_a_string_list():
    assert settings_schema()["reason"]["verdict_policy_params"]["type"] == "string_list"


def test_the_schema_uses_yaml_section_names():
    assert list(settings_schema()) == ["gather", "reason", "validate", "review", "session_service"]


def test_every_setting_is_described():
    for fields in settings_schema().values():
        for meta in fields.values():
            assert meta["description"]


def test_errors_of_lists_every_ordering_problem_one_per_line():
    raw = _raw()
    raw["steps"].remove("reason")
    raw["steps"].remove("validate")
    with pytest.raises(ValidationError) as exc:
        WorkflowConfig.model_validate(raw)
    errs = errors_of(exc.value)
    assert any("'reason' cannot be removed" in e for e in errs)
    assert any("'validate' cannot be removed" in e for e in errs)
    assert not any(e.startswith("- ") for e in errs)


def test_errors_of_names_the_field_of_a_misspelt_setting():
    raw = _raw()
    raw["settings"]["gather"]["prior_lookback_days"] = 90
    with pytest.raises(ValidationError) as exc:
        WorkflowConfig.model_validate(raw)
    assert errors_of(exc.value) == [
        "settings.gather.prior_lookback_days: Extra inputs are not permitted"
    ]
