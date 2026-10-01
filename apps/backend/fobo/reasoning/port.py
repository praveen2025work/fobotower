"""The reasoning port.

This application orchestrates; it does not own the model call. Reasoning is
delegated through a port so the transport — an existing session service, a
direct SDK call, or nothing at all — is a deployment choice rather than a
code change.

The port is rec-level: one request per L4 rec run, not one per break. A rec
can carry thousands of breaks, and a model call (or agent session) per break
is neither affordable nor fast; breaks are grouped into patterns and the
agent answers per pattern, plus exceptions. Because an agent session can
outlast one HTTP call, the port is start-then-poll. There is no partial
success: a verdict the caller cannot trust is worse than an escalation.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from fobo.reasoning.contracts import RecVerdict


class ReasoningUnavailable(RuntimeError):
    """The reasoner could not produce a verdict.

    Raised rather than returning a degraded answer: R6 says an unevidenced
    conclusion is an escalation outcome, and a silent fallback manufactures
    exactly that.
    """


@dataclass(frozen=True)
class HarnessStatus:
    """Where one agent session stands. `output` is set only once completed;
    `error` only when failed (a failed session is data for the step to
    record, not an exception)."""

    session_id: str
    status: Literal["running", "completed", "failed"]
    output: RecVerdict | None = None
    payload: dict = field(default_factory=dict)
    error: str | None = None


class ReasoningPort(Protocol):
    """What the orchestrator needs from whatever performs the reasoning."""

    name: str

    async def start(self, request: dict) -> HarnessStatus:
        """Open one agent session for a rec's unsettled breaks."""
        ...

    async def poll(self, session_id: str) -> HarnessStatus:
        """Check a session started earlier. Waiting and sleeping live in the
        caller, so adapters stay a single request each."""
        ...
