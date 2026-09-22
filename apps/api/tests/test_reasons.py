import pytest

from app.recon.reasons import PATTERN_REASONS, reason_for
from app.workflow.nodes.group import PATTERNS


def test_the_mock_wording_for_each_pattern():
    assert reason_for("C1") == "Nostro statement received after 23:30 cutoff"
    assert reason_for("C2") == "Reference does not resolve in static data"
    assert reason_for("C5") == "Pending desk confirmation since the 11:00 run"
    assert reason_for("C6") == "Two entries with identical settlement reference"


def test_every_cause_check_has_controller_facing_wording():
    """A break with no readable reason is a blank cell on the screen."""
    for check_id in ("C1", "C2", "C3", "C4", "C5", "C6"):
        assert reason_for(check_id), f"{check_id} has no reason text"


def test_every_pattern_code_has_wording():
    for _check, (code, _label, _mode) in PATTERNS.items():
        assert code in PATTERN_REASONS, f"{code} has no reason text"


def test_an_unknown_check_raises_rather_than_returning_blank():
    with pytest.raises(KeyError):
        reason_for("C99")
