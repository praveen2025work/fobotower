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

from fobo.reasoning.adapters.null import NullReasoner
from fobo.reasoning.port import ReasoningPort, ReasoningUnavailable


def get_reasoner() -> ReasoningPort:
    from fobo.investigation.settings import settings

    # The environment wins, so a deployment can override the file.
    choice = (os.getenv("FOBO_REASONER") or settings().reason.reasoner).strip().lower()
    if choice == "session_service":
        from fobo.reasoning.adapters.session_service import SessionServiceReasoner

        return SessionServiceReasoner()
    if choice == "direct":
        from fobo.reasoning.adapters.direct import DirectReasoner

        return DirectReasoner()
    if choice == "none":
        return NullReasoner()
    raise ReasoningUnavailable(f"unknown FOBO_REASONER: {choice!r}")
