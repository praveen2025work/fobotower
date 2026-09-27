import pytest
from pydantic import ValidationError

from fobo.contracts.models import Caller, PatternGroup


def test_caller_requires_entity_scope():
    c = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE1"], region="APAC")
    assert c.entity_scope == ["LE1"]


def test_strict_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        PatternGroup(
            group_id="g1",
            pattern_code="P-1",
            label="test",
            mode="auto",
            break_ids=["b1"],
            surprise=True,
        )
