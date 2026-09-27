"""The board's efficiency tile.

Every tile derives from rows. Where a figure rests on an assumption — the
minutes a manual decision would have cost — that assumption is returned
alongside the number, so the tile can show its own basis rather than
asserting a total nobody can check.
"""

from datetime import date

from sqlalchemy import func, select

from fobo.db.models_graph import BreakEvent

# What one manual decision would have cost a controller. Declared, not
# measured — and surfaced with the estimate it feeds.
MANUAL_MINUTES_PER_DECISION = 12


async def decisions_saved(session, business_date: date) -> dict:
    """Breaks that would each have been a decision, against the number of
    pattern groups they collapsed into. This is the efficiency claim."""
    breaks = int(
        await session.scalar(
            select(func.count())
            .select_from(BreakEvent)
            .where(BreakEvent.cob_date == business_date)
        )
        or 0
    )
    groups = int(
        await session.scalar(
            select(func.count(func.distinct(BreakEvent.pattern_code))).where(
                BreakEvent.cob_date == business_date,
                BreakEvent.pattern_code.isnot(None),
            )
        )
        or 0
    )
    return {
        "from": breaks,
        "to": groups,
        "basis": f"{breaks} breaks grouped into {groups} patterns",
    }


async def hours_saved(session, business_date: date) -> dict:
    saved = await decisions_saved(session, business_date)
    avoided = max(0, saved["from"] - saved["to"])
    hours = round(avoided * MANUAL_MINUTES_PER_DECISION / 60, 1)
    return {
        "value": hours,
        "basis": (
            f"{avoided} decisions avoided at "
            f"{MANUAL_MINUTES_PER_DECISION} min each"
        ),
    }
