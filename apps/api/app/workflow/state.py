from datetime import date
from typing import Any, TypedDict

from app.contracts.models import AnalysisDraft, Caller, CandidateCause, PatternGroup

MAX_HYPOTHESIS_ATTEMPTS = 3
MAX_REVIEW_CYCLES = 2


class InvestigationState(TypedDict, total=False):
    """Session-grained, not break-grained.

    thread_id = investigation_session_id at rec/book/run grain, so the review
    interrupt fires once per session and the controller approves per pattern
    group. A per-break thread could not offer group approval at all.
    """

    # Identity
    investigation_session_id: str
    reconciliation_id: str
    master_book: str
    business_date: date
    run_id: str
    caller: Caller

    # Population
    breaks: list[dict]
    book_resolutions: dict[str, str]
    as_of: date

    # Gather
    deltas: dict[str, float]
    candidates: dict[str, list[CandidateCause]]
    priors: dict[str, list[dict]]
    lineage: dict[str, list[dict]]
    evidence_gaps: list[str]

    # Group / rank / draft
    pattern_groups: list[PatternGroup]
    reasons: dict[str, str]
    group_meta: dict[str, dict]
    ranking: dict[str, Any]
    model_skipped: bool
    draft: AnalysisDraft | None
    validation_errors: list[str]
    hypothesis_attempts: int

    # Review
    review_cycles: int
    decisions: list[dict]

    # Outcome
    outcome: str | None
    escalation_reason: str | None
