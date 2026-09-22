"""Produce the four-part narrative: what happened, why, what to do, risk.

Phase 1 renders a deterministic template over grounded values, so every
figure traces to a delta by construction. Phase 3 replaces the body with a
model call under a 400-token cap. The validator does not change when it
does — that is the point of validating the output rather than trusting the
producer.
"""

from app.contracts.models import AnalysisDraft
from app.workflow.state import InvestigationState


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or f"{singular}s")


# Percentages read aloud: 8, 11, 18 and the 80s take "an", the rest take "a".
_AN_PREFIXES = ("8", "11", "18")


def _article(percent: int) -> str:
    return "an" if str(percent).startswith(_AN_PREFIXES) else "a"


async def draft(state: InvestigationState, *, session) -> dict:
    groups = state["pattern_groups"]
    breaks = state["breaks"]
    n_breaks = len(breaks)
    n_books = len({b["book_ref"] for b in breaks})
    n_groups = len(groups)

    what_happened = (
        f"{n_breaks} {_plural(n_breaks, 'break')} across "
        f"{n_books} {_plural(n_books, 'book')}, grouped into "
        f"{n_groups} distinct root {_plural(n_groups, 'cause')}."
    )

    why = " ".join(
        f"{len(g.break_ids)} attributed to {g.label} ({g.pattern_code}), "
        f"totalling {_money(sum(state['deltas'].get(b, 0.0) for b in g.break_ids))}."
        for g in groups
    )

    auto = [g for g in groups if g.mode == "auto"]
    what_to_do = (
        f"Approve the {auto[0].pattern_code} group in one action. " if auto else ""
    ) + "Review the remaining groups individually before approving."

    gaps = state.get("evidence_gaps", [])
    risk = (
        f"{len(gaps)} evidence {_plural(len(gaps), 'gap')} on this run: "
        f"{', '.join(gaps)}. Verify affected figures manually."
        if gaps
        else "No evidence gaps on this run."
    )

    rated = [g for g in groups if g.historical_approval_rate is not None]
    confidence_basis = (
        " ".join(
            f"{g.pattern_code} has {_article(round(g.historical_approval_rate * 100))} "
            f"{g.historical_approval_rate:.0%} historical approval rate."
            for g in rated
        )
        or "No prior resolutions available for these patterns."
    )

    return {
        "draft": AnalysisDraft(
            what_happened=what_happened,
            why=why,
            what_to_do=what_to_do,
            risk=risk,
            confidence_basis=confidence_basis,
        )
    }
