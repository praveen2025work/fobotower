"""Skill-driven reasoning over one break."""

import json

from app.reasoning.client import (
    MAX_TOKENS,
    MODEL,
    ReasoningUnavailable,
    build_client,
    system_blocks,
)
from app.reasoning.contracts import SkillVerdict


def _evidence_prompt(record: dict) -> str:
    """The break record, as evidence. Everything the model may cite."""
    return (
        "Investigate this break by the skill's master sequence.\n\n"
        "```json\n" + json.dumps(record, indent=2, default=str) + "\n```\n\n"
        "Produce the §12 output. Where the record does not contain what a test "
        "needs, record that test as 'Unable to test' with the evidence you "
        "would need."
    )


async def reason_over_break(record: dict) -> SkillVerdict:
    """Apply the skill to one break and return its structured verdict.

    Raises ReasoningUnavailable when there is no credential — the caller
    degrades to the deterministic path and flags an evidence gap rather than
    presenting a guess.
    """
    client = build_client()
    try:
        response = await client.messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=system_blocks(),
            messages=[{"role": "user", "content": _evidence_prompt(record)}],
            output_format=SkillVerdict,
        )
    except Exception as exc:  # noqa: BLE001 — surfaced, never swallowed
        raise ReasoningUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise ReasoningUnavailable("model declined to answer this break")

    parsed = response.parsed_output
    if parsed is None:
        raise ReasoningUnavailable("model returned no parseable verdict")
    return parsed
