"""Single source of truth for the entity contract."""

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
