import copy

import pytest
import yaml
from pydantic import ValidationError

from app.playbook.loader import DEFAULT_PATH, loaded_version, load_playbook, read_playbook
from app.playbook.schema import Playbook
from app.db.base import get_session


def _raw():
    return yaml.safe_load(DEFAULT_PATH.read_text())


def _invalid(mutate):
    raw = copy.deepcopy(_raw())
    mutate(raw)
    with pytest.raises((ValidationError, ValueError)) as exc:
        Playbook.model_validate(raw)
    return str(exc.value)


def test_the_checked_in_playbook_is_valid():
    pb = read_playbook()
    assert pb.version == "1.0"
    assert len(pb.tests) == 14


def test_a_dependency_on_an_unknown_test_is_rejected():
    msg = _invalid(lambda r: r["tests"]["FO-3"].update(requires_on_fail=["FO-9"]))
    assert "unknown test 'FO-9'" in msg


def test_a_finding_indicating_an_unknown_category_is_rejected():
    msg = _invalid(lambda r: r["findings"]["A"].update(indicates="Z"))
    assert "unknown category 'Z'" in msg


def test_a_misspelt_escalation_team_is_rejected():
    msg = _invalid(lambda r: r["categories"]["C"].update(escalate_to="CATS Suport"))
    assert "unknown team 'CATS Suport'" in msg


def test_an_fo_side_default_of_post_is_rejected():
    """R2 in the data: a playbook that lets an FO cause post must not load,
    even though the guards would block it at runtime anyway."""
    msg = _invalid(lambda r: r["default_verdicts"]["C"].update(FO="POST"))
    assert "breaks R2" in msg


def test_a_test_validating_a_component_on_the_wrong_side_is_rejected():
    msg = _invalid(lambda r: r["tests"]["FO-1"].update(validates="Journal Generation"))
    assert "not a FO component" in msg


def test_an_unknown_field_is_rejected_rather_than_ignored():
    """A typo in a key name must not silently drop a rule."""
    msg = _invalid(lambda r: r["tests"]["FO-3"].update(requires_onfail=["FO-6"]))
    assert "requires_onfail" in msg


def test_every_problem_is_reported_not_just_the_first():
    def two(r):
        r["categories"]["B"]["escalate_to"] = "Nobody"
        r["categories"]["C"]["escalate_to"] = "Nobody"
    msg = _invalid(two)
    assert "category B" in msg and "category C" in msg


def test_a_cause_check_side_must_be_fo_bo_or_unknown():
    msg = _invalid(lambda r: r["cause_checks"]["C1"].update(side="MAYBE"))
    assert "side" in msg


def test_policy_values_start_unset():
    """Rule P1: until Product Control supplies a value it is unknown."""
    pb = read_playbook()
    assert all(p.value is None for p in pb.policy.values())


async def test_loading_records_the_version():
    async with get_session() as s:
        await load_playbook(s)
        assert await loaded_version(s) == "1.0"


async def test_reloading_replaces_rather_than_duplicates():
    async with get_session() as s:
        await load_playbook(s)
        await load_playbook(s)
        assert await loaded_version(s) == "1.0"
