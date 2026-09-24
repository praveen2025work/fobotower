"""What changed between two versions, and re-applying a stale draft."""

import copy

from app.workflow.config import dump_config, read_workflow
from app.workflow.diff import Change, diff, rebase


def _base() -> dict:
    return dump_config(read_workflow())


def _with(cfg: dict, *edits) -> dict:
    out = copy.deepcopy(cfg)
    for edit in edits:
        edit(out)
    return out


def _lookback(days):
    return lambda c: c["settings"]["gather"].update(priors_lookback_days=days)


def _move(step, to):
    def edit(c):
        c["steps"].remove(step)
        c["steps"].insert(to, step)
    return edit


def test_identical_configs_have_no_changes():
    assert diff(_base(), _base()) == []


def test_a_removed_step_names_its_old_position():
    other = _with(_base(), lambda c: c["steps"].remove("rank"))
    assert diff(_base(), other) == [Change("steps.rank", "removed", before=4, after=None)]


def test_an_added_step_names_its_new_position():
    without = _with(_base(), lambda c: c["steps"].remove("rank"))
    assert diff(without, _base()) == [Change("steps.rank", "added", before=None, after=4)]


def test_moving_one_step_reports_only_that_step():
    other = _with(_base(), _move("rank", 6))
    assert diff(_base(), other) == [Change("steps.rank", "moved", before=4, after=6)]


def test_pauses_added_and_removed():
    other = _with(_base(), lambda c: c.update(pause_before=["reason"]))
    assert diff(_base(), other) == [
        Change("pause_before.review", "removed"),
        Change("pause_before.reason", "added"),
    ]


def test_a_changed_setting_carries_both_values():
    assert diff(_base(), _with(_base(), _lookback(90))) == [
        Change("settings.gather.priors_lookback_days", "changed", before=180, after=90)
    ]


def test_changes_are_plain_dicts_for_the_api():
    assert Change("steps.rank", "removed", before=4).as_dict() == {
        "path": "steps.rank", "kind": "removed", "before": 4, "after": None,
    }


def test_rebase_keeps_the_drafts_change_and_the_active_versions_change():
    base = _base()
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    active = _with(base, _lookback(90))
    merged, conflicts = rebase(base, draft, active)
    assert "rank" not in merged["steps"]
    assert merged["settings"]["gather"]["priors_lookback_days"] == 90
    assert conflicts == []


def test_rebase_reports_a_setting_both_sides_changed_and_keeps_the_drafts_value():
    base = _base()
    merged, conflicts = rebase(base, _with(base, _lookback(30)), _with(base, _lookback(90)))
    assert merged["settings"]["gather"]["priors_lookback_days"] == 30
    assert conflicts == ["settings.gather.priors_lookback_days"]


def test_rebase_is_quiet_when_both_sides_made_the_same_change():
    base = _base()
    _, conflicts = rebase(base, _with(base, _lookback(90)), _with(base, _lookback(90)))
    assert conflicts == []


def test_rebase_reports_a_step_list_both_sides_changed():
    base = _base()
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    active = _with(base, _move("rank", 6))
    merged, conflicts = rebase(base, draft, active)
    assert "rank" not in merged["steps"] and conflicts == ["steps"]


def test_rebase_does_not_change_its_inputs():
    base, active = _base(), _with(_base(), _lookback(90))
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    before = copy.deepcopy((base, draft, active))
    rebase(base, draft, active)
    assert (base, draft, active) == before
