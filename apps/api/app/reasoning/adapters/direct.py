"""Direct Anthropic SDK reasoner — for local development only.

Production reasoning goes through the session service, which owns the skill,
file inputs and MCP tool wiring. This adapter exists so the orchestration can
be exercised end to end without that service.
"""

import json

import anthropic

from app.reasoning.contracts import SkillVerdict
from app.reasoning.port import ReasoningUnavailable
from app.reasoning.prompt import reasoning_prompt

MODEL = "claude-opus-5"
MAX_TOKENS = 8000


class DirectReasoner:
    name = "direct"

    def __init__(self):
        try:
            self._client = anthropic.AsyncAnthropic()
        except Exception as exc:  # noqa: BLE001
            raise ReasoningUnavailable(f"no Anthropic credential: {exc}") from exc

    async def investigate(self, evidence: dict) -> SkillVerdict:
        try:
            response = await self._client.messages.parse(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                system=reasoning_prompt(),
                messages=[{
                    "role": "user",
                    "content": "```json\n" + json.dumps(evidence, indent=2, default=str)
                    + "\n```",
                }],
                output_format=SkillVerdict,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
            raise ReasoningUnavailable(str(exc)) from exc
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ReasoningUnavailable("no usable verdict returned")
        return response.parsed_output
