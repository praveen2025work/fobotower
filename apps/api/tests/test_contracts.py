import json

import pytest
from pydantic import ValidationError

from app.contracts.models import WS_EVENT_MODELS, BreakRecord, Caller, RunProgress


def test_caller_requires_entity_scope():
    c = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE1"], region="APAC")
    assert c.entity_scope == ["LE1"]


def test_every_ws_event_declares_a_literal_type():
    for model in WS_EVENT_MODELS:
        schema = model.model_json_schema()
        assert "type" in schema["properties"], f"{model.__name__} has no type field"
        assert "const" in schema["properties"]["type"], (
            f"{model.__name__} type is not a literal"
        )


def test_run_progress_round_trips_through_json_schema():
    evt = RunProgress(
        session_id="s1", node="gather", breaks_processed=3, breaks_total=14
    )
    payload = json.loads(evt.model_dump_json())
    assert RunProgress.model_validate(payload) == evt


def test_break_record_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        BreakRecord(
            break_id="b1",
            book_ref="APAC-CASH-01",
            line_code="CASH",
            cob_date="2026-08-03",
            fo_value=1.0,
            bo_value=2.0,
            surprise=True,
        )
