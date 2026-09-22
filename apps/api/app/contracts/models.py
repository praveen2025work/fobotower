"""Single source of truth for the event and entity contract.

Generated into JSON Schema and .d.ts by packages/contracts/build.py.
The console validates inbound events against the generated schema.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Union

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


# ---------- websocket events ----------


class RunProgress(Strict):
    type: Literal["run.progress"] = "run.progress"
    session_id: str
    node: str
    breaks_processed: int
    breaks_total: int


class ApprovalRequired(Strict):
    type: Literal["approval.required"] = "approval.required"
    session_id: str
    group_id: str
    pattern_code: str
    break_ids: list[str]
    historical_approval_rate: float | None = None


class EvidenceRegistered(Strict):
    type: Literal["evidence.registered"] = "evidence.registered"
    session_id: str
    evidence_id: str
    source_application: str
    retrieved_ts: datetime
    is_original_analysis: bool


class AnalysisVersionEvent(Strict):
    type: Literal["analysis.version"] = "analysis.version"
    session_id: str
    analysis_version_id: str
    supersedes: str | None = None


class DecisionRecorded(Strict):
    type: Literal["decision.recorded"] = "decision.recorded"
    session_id: str
    decision_id: str
    action: Literal["approve", "reject", "escalate"]
    reason: str | None = None
    idempotency_key: str


class ErrorEvent(Strict):
    type: Literal["error"] = "error"
    session_id: str | None = None
    code: str
    message: str
    application: str | None = None
    recoverable: bool


WS_EVENT_MODELS = [
    RunProgress,
    ApprovalRequired,
    EvidenceRegistered,
    AnalysisVersionEvent,
    DecisionRecorded,
    ErrorEvent,
]

WsEvent = Annotated[
    Union[
        RunProgress,
        ApprovalRequired,
        EvidenceRegistered,
        AnalysisVersionEvent,
        DecisionRecorded,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
