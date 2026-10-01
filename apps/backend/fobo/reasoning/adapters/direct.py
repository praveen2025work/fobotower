"""Direct Anthropic SDK reasoner — for local development only.

Production reasoning goes through the session service, which owns the skill,
file inputs and MCP tool wiring. This adapter exists so the orchestration can
be exercised end to end without that service. It answers `start` with one
synchronous model call over the request's inputs, so the session is already
completed and there is nothing to poll.
"""

import json
import uuid

import anthropic

from fobo.reasoning.contracts import RecVerdict
from fobo.reasoning.port import HarnessStatus, ReasoningUnavailable
from fobo.reasoning.prompt import reasoning_prompt

MODEL = "claude-opus-5-5"
MAX_TOKENS = 8000


class DirectReasoner:
    name = "direct"

    def __init__(self):
        try:
            self._client = anthropic.AsyncAnthropic()
        except Exception as exc:  # noqa: BLE001
            raise ReasoningUnavailable(f"no Anthropic credential: {exc}") from exc

    async def start(self, request: dict) -> HarnessStatus:
        try:
            response = await self._client.messages.parse(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                system=reasoning_prompt(),
                messages=[{
                    "role": "user",
                    "content": "```json\n"
                    + json.dumps(request.get("inputs", {}), indent=2, default=str)
                    + "\n```",
                }],
                output_format=RecVerdict,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
            raise ReasoningUnavailable(str(exc)) from exc
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ReasoningUnavailable("no usable verdict returned")
        return HarnessStatus(
            session_id=f"direct-{uuid.uuid4().hex[:12]}",
            status="completed",
            output=response.parsed_output,
            payload={},
        )

    async def poll(self, session_id: str) -> HarnessStatus:
        raise ReasoningUnavailable("direct reasoner completes synchronously")
