import pytest
from pydantic import ValidationError

from app.contracts.models import BreakRecord, Caller


def test_caller_requires_entity_scope():
    c = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE1"], region="APAC")
    assert c.entity_scope == ["LE1"]


def test_break_record_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        BreakRecord(
            break_id="b1",
            book_ref="PRIME-MB-01",
            line_code="CASH",
            cob_date="2026-08-03",
            fo_value=1.0,
            bo_value=2.0,
            surprise=True,
        )
