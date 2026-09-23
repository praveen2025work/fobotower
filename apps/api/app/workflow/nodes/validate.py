"""Hard assertions before a human ever sees the draft.

Every figure in the narrative must trace back to a computed delta. This is
the numeric-grounding validator, and its pass rate is what the analytics tab
reports. That rate measures grounding, not model confidence — the two are
different things and must stay labelled differently.
"""

import re

from app.workflow.config import settings
from app.workflow.state import InvestigationState

MONEY = re.compile(r"\$([\d,]+\.\d{2})")


def _grounded_values(state: InvestigationState) -> set[str]:
    """Every value a draft is permitted to cite: per-break deltas and the
    group totals derived from them."""
    deltas = state.get("deltas", {})
    values = {f"{v:,.2f}" for v in deltas.values()}
    for g in state.get("pattern_groups", []):
        total = sum(deltas.get(b, 0.0) for b in g.break_ids)
        values.add(f"{total:,.2f}")
    return values


async def validate(state: InvestigationState, *, session) -> dict:
    d = state.get("draft")
    if d is None:
        return {"validation_errors": ["no draft produced"]}

    errors: list[str] = []
    grounded = _grounded_values(state)
    text = " ".join([d.what_happened, d.why, d.what_to_do, d.risk])

    for found in MONEY.findall(text):
        if found not in grounded:
            errors.append(f"ungrounded figure: ${found}")

    for g in state.get("pattern_groups", []):
        if not g.break_ids:
            errors.append(f"empty pattern group: {g.pattern_code}")

    for gap in state.get("evidence_gaps", []):
        errors.append(f"evidence_gap: {gap}")

    if state.get("hypothesis_attempts", 0) >= settings().validate_.max_hypothesis_attempts:
        errors.append("RETRY_EXHAUSTED")

    return {"validation_errors": errors}
