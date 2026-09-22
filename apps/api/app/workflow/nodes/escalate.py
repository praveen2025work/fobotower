"""Terminal. Sets the reason code and preserves all gathered evidence.

The reason must be one of the known codes. An unrecognised code means a
caller invented one, and an escalation nobody can route is worse than a
loud failure here.
"""

from app.workflow.state import InvestigationState

REASONS = {
    "UNRESOLVED_BOOK",
    "AMBIGUOUS_BOOK",
    "UNMAPPED_BOOK",
    "DELTA_UNAVAILABLE",
    "CHECKS_UNAVAILABLE",
    "RETRY_EXHAUSTED",
    "VALIDATION_FAILED",
}


async def escalate(state: InvestigationState) -> dict:
    reason = state.get("escalation_reason")
    if reason not in REASONS:
        raise ValueError(f"unknown escalation reason: {reason}")
    return {"outcome": "escalated", "escalation_reason": reason}
