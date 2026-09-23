"""No reasoner configured.

The honest default. Every judgement-based break escalates, which is the
correct outcome when nothing is available to reason with — and it makes the
absence visible in the analytics rather than silently degrading into the
deterministic guess.
"""

from app.reasoning.contracts import SkillVerdict
from app.reasoning.port import ReasoningUnavailable


class NullReasoner:
    name = "none"

    async def investigate(self, evidence: dict) -> SkillVerdict:
        raise ReasoningUnavailable(
            "no reasoner configured — set FOBO_REASONER to route judgement-based "
            "breaks to the session service"
        )
