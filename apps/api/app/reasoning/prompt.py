"""The reasoning prompt — what is left of the skill after extraction.

Control flow now lives in the LangGraph wiring, computation in the engines,
rules and taxonomy in the knowledge graph, and thresholds in policy nodes.
What remains is guidance only a reasoner can use: role, evidence discipline,
how to frame competing hypotheses, and the output format.

Kept deliberately short. Anything restated here that the graph also enforces
is a second source of truth, and the two will drift.
"""

from pathlib import Path

SKILL_PATH = (
    Path(__file__).resolve().parents[4]
    / "docs" / "skills" / "fobo-investigation-cats-vs-motif.md"
)


def reasoning_prompt() -> list[dict]:
    return [
        {
            "type": "text",
            "text": SKILL_PATH.read_text(encoding="utf-8"),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "The orchestrator has already run every deterministic check it can "
                "and could not settle this break. It reaches you because it is "
                "judgement-based: multiple causes fired, or none did.\n\n"
                "Your job is to frame the competing hypotheses, weigh the evidence "
                "for each, and recommend — not assert — a verdict. The orchestrator "
                "will apply the posting rules itself; do not rely on your verdict "
                "surviving if it conflicts with them.\n\n"
                "Cite only evidence present in the record. Where a test could not "
                "run, say so and name the evidence that would settle it."
            ),
        },
    ]
