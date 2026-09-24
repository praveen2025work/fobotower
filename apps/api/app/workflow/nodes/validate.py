"""Hard assertions before a human ever sees the draft.

Every figure in the narrative must trace back to a computed delta. This is
the numeric-grounding validator, and its pass rate is what the analytics tab
reports. That rate measures grounding, not model confidence — the two are
different things and must stay labelled differently.
"""

import re
import time

from app.grounding.recorder import GroundingRecorder
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


def _grounding_rows(state: InvestigationState) -> list[dict]:
    """Each drafted figure against the MB Rec value it must trace to. A break
    flagged ungrounded has a figure with no matching source value."""
    ungrounded = set(state.get("ungrounded_breaks", []))
    deltas = state.get("deltas", {})
    rows = []
    for brk in state.get("breaks", []):
        bid = brk["break_id"]
        if bid not in deltas:
            continue
        traced = bid not in ungrounded
        rows.append(
            {
                "adjId": bid,
                "figure": deltas[bid],
                "source": deltas[bid] if traced else None,
                "result": "Traced" if traced else "Not traced",
            }
        )
    return rows


async def _record_grounding(state: InvestigationState, session) -> None:
    started = time.perf_counter()
    rows = _grounding_rows(state)
    failed = sum(1 for r in rows if r["result"] != "Traced")
    await GroundingRecorder(session, state["investigation_session_id"]).record(
        application="Helix",
        tool="helix.grounding_check",
        params={"rec": state["reconciliation_id"], "figures": len(rows)},
        row_count=len(rows),
        summary=f"{failed} not traced" if failed else f"{len(rows)} of {len(rows)} traced",
        latency_ms=round((time.perf_counter() - started) * 1000),
        rows=rows,
    )


async def validate(state: InvestigationState, *, session) -> dict:
    d = state.get("draft")
    if d is None:
        return {"validation_errors": ["no draft produced"]}
    # Validation itself is pure; only a live run has a session to record into.
    if session is not None:
        await _record_grounding(state, session)

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
