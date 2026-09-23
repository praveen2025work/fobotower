"""Selects the reasoner from configuration.

FOBO_REASONER:
    session_service   the existing session service (production)
    direct            direct Anthropic SDK call (local development)
    none              no reasoner; judgement-based breaks escalate (default)

Defaulting to none is deliberate. A reasoner silently falling back to
another would make it impossible to tell, from the output, which one
produced a verdict.
"""

import os

from app.reasoning.adapters.null import NullReasoner
from app.reasoning.port import ReasoningPort, ReasoningUnavailable


def get_reasoner() -> ReasoningPort:
    from app.workflow.config import settings

    # The environment wins, so a deployment can override the file.
    choice = (os.getenv("FOBO_REASONER") or settings().reason.reasoner).strip().lower()
    if choice == "session_service":
        from app.reasoning.adapters.session_service import SessionServiceReasoner

        return SessionServiceReasoner()
    if choice == "direct":
        from app.reasoning.adapters.direct import DirectReasoner

        return DirectReasoner()
    if choice == "none":
        return NullReasoner()
    raise ReasoningUnavailable(f"unknown FOBO_REASONER: {choice!r}")
