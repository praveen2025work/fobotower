"""The reasoning port.

This application orchestrates; it does not own the model call. Reasoning is
delegated through a port so the transport — an existing session service, a
direct SDK call, or nothing at all — is a deployment choice rather than a
code change.

The port's contract is deliberately narrow: hand over one break's evidence,
get back a §12 verdict, or raise. There is no partial success. A verdict the
caller cannot trust is worse than an escalation.
"""

from typing import Protocol

from app.reasoning.contracts import SkillVerdict


class ReasoningUnavailable(RuntimeError):
    """The reasoner could not produce a verdict.

    Raised rather than returning a degraded answer: R6 says an unevidenced
    conclusion is an escalation outcome, and a silent fallback manufactures
    exactly that.
    """


class ReasoningPort(Protocol):
    """What the orchestrator needs from whatever performs the reasoning."""

    name: str

    async def investigate(self, evidence: dict) -> SkillVerdict:
        """Apply the FOBO investigation skill to one break's evidence.

        `evidence` carries only what the break record and the graph already
        established — never the whole run. Keeping the payload to one break
        is what makes the escalation auditable: every figure in the verdict
        must trace to something in here.
        """
        ...
