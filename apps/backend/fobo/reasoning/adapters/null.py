"""No reasoner configured.

The honest default. Every judgement-based break escalates, which is the
correct outcome when nothing is available to reason with — and it makes the
absence visible in the analytics rather than silently degrading into the
deterministic guess.
"""

from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable

NO_REASONER_MESSAGE = (
    "no reasoner configured — set FOBO_REASONER to route judgement-based "
    "breaks to the session service"
)


class NullReasoner:
    name = "none"

    async def start(self, request: dict) -> HarnessStatus:
        raise ReasoningUnavailable(NO_REASONER_MESSAGE)

    async def poll(self, session_id: str) -> HarnessStatus:
        raise ReasoningUnavailable(NO_REASONER_MESSAGE)
