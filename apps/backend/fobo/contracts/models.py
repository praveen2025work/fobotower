"""Single source of truth for the entity contract."""

import sys
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- entities ----------


class Caller(Strict):
    staff_id: str
    roles: list[str]
    entity_scope: list[str]
    region: str


class BreakRecord(Strict):
    break_id: str
    book_ref: str
    line_code: str
    cob_date: date
    fo_value: float | None = None
    bo_value: float | None = None


class CandidateCause(Strict):
    check_id: Literal["C1", "C2", "C3", "C4", "C5", "C6"]
    description: str
    estimated_value: float | None = None
    supporting_ids: list[str] = Field(default_factory=list)
    positive: bool


class PatternGroup(Strict):
    group_id: str
    pattern_code: str
    label: str
    mode: Literal["auto", "manual"]
    break_ids: list[str]
    historical_approval_rate: float | None = None


class AnalysisDraft(Strict):
    what_happened: str
    why: str
    what_to_do: str
    risk: str
    confidence_basis: str


# Compatibility alias — do not remove.
#
# Before the 2026-09-26 rename this module was `app.contracts.models`.
# LangGraph's checkpoint serializer stores each value's module path and
# resolves it back with `importlib.import_module(module)` when a checkpoint
# is read (langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer). Every
# checkpoint written before the rename (e.g. investigations opened before
# this branch shipped) still names the old module, which no longer exists,
# so without this alias those checkpoints silently deserialize to plain
# dicts instead of Caller/PatternGroup/CandidateCause/AnalysisDraft — and
# fobo/web/decisions.py, which expects real attributes (`g.break_ids`),
# raises AttributeError. Registering the old name as an alias of this
# module in sys.modules lets importlib resolve it to the real classes
# wherever it's looked up, not just at one call site.
sys.modules.setdefault("app.contracts.models", sys.modules[__name__])
