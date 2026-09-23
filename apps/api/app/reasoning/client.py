"""Claude client for skill-driven break reasoning.

The skill document is the system prompt. It is long and identical on every
request, so it carries a cache breakpoint: the volatile per-break evidence
goes after it, in the user turn.
"""

import os
from pathlib import Path

import anthropic

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

# docs/skills/... relative to the repo root, from apps/api/app/reasoning/.
SKILL_PATH = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "skills"
    / "fobo-investigation-cats-vs-motif.md"
)


class ReasoningUnavailable(RuntimeError):
    """No credential, or the model could not be reached.

    Raised rather than falling back to a guess: R6 says an unevidenced
    conclusion is an escalation, and a silent fallback would produce one.
    """


def skill_text() -> str:
    if not SKILL_PATH.exists():
        raise ReasoningUnavailable(f"skill document not found at {SKILL_PATH}")
    return SKILL_PATH.read_text(encoding="utf-8")


def credentials_available() -> bool:
    return bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    )


def build_client() -> anthropic.AsyncAnthropic:
    if not credentials_available():
        raise ReasoningUnavailable(
            "no ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN; "
            "skill-driven reasoning is disabled"
        )
    return anthropic.AsyncAnthropic()


def system_blocks() -> list[dict]:
    """System prompt: the skill, then the operating instruction.

    cache_control on the skill block — it is ~15k tokens, unchanged between
    requests, and every break in a run re-sends it.
    """
    return [
        {
            "type": "text",
            "text": skill_text(),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "You are applying the skill above to one reconciliation break.\n\n"
                "Hard constraints:\n"
                "- R2: validate Front Office before Back Office. Never assume FO "
                "is correct.\n"
                "- R6: if you cannot evidence it, the verdict is ESCALATE and "
                "root_cause.established is false. Do not assert an unevidenced "
                "cause.\n"
                "- R7: if the break is judgement-based, set requires_sme_review "
                "true, populate competing_hypotheses, and present the verdict as "
                "a recommendation.\n"
                "- Rule P1: never invent a threshold. If a conclusion depends on a "
                "local parameter that was not supplied, name it in "
                "unset_parameters and state the conclusion conditionally.\n"
                "- Only cite evidence that appears in the break record given to "
                "you. If a test could not be run, mark it 'Unable to test' and "
                "say what evidence would settle it."
            ),
        },
    ]
