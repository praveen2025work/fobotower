"""Agent analytics.

Every tile derives from rows. Where a figure rests on an assumption — the
minutes a manual decision would have cost — that assumption is returned
alongside the number, so the tile can show its own basis rather than
asserting a total nobody can check.
"""

from datetime import date, timedelta

from sqlalchemy import Integer, case, cast, func, select

from app.db.models_graph import BreakEvent
from app.db.models_ops import Reconciliation, Run, SourceCall
from app.db.models_session import ControllerDecision, InvestigationSession

# What one manual decision would have cost a controller. Declared, not
# measured — and surfaced with the estimate it feeds.
MANUAL_MINUTES_PER_DECISION = 12


async def grounding_pass_rate(session, business_date: date) -> dict:
    """Share of retrievals that returned data rather than failing.

    This measures grounding, not model confidence. They are different things
    and must stay labelled differently.
    """
    total = int(
        await session.scalar(select(func.count()).select_from(SourceCall)) or 0
    )
    failed = int(
        await session.scalar(
            select(func.count())
            .select_from(SourceCall)
            .where(SourceCall.error_detail.isnot(None))
        )
        or 0
    )
    if total == 0:
        return {"value": None, "basis": "no retrievals recorded"}
    rate = round((total - failed) / total * 100, 1)
    return {"value": rate, "basis": f"{total - failed} of {total} retrievals"}


async def draft_acceptance(session, business_date: date) -> dict:
    """Share of decisions that approved the draft as written."""
    rows = (
        await session.execute(
            select(ControllerDecision.action, func.count()).group_by(
                ControllerDecision.action
            )
        )
    ).all()
    counts = dict(rows)
    total = sum(counts.values())
    if total == 0:
        return {"value": None, "basis": "no decisions recorded"}
    approved = counts.get("approve", 0)
    return {
        "value": round(approved / total * 100, 1),
        "basis": f"{approved} of {total} decisions",
    }


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


async def median_signoff_minutes(session, business_date: date) -> dict:
    """Median minutes from a session opening to its decision being recorded."""
    stmt = (
        select(
            cast(
                func.extract(
                    "epoch",
                    ControllerDecision.decided_ts - InvestigationSession.created_ts,
                )
                / 60,
                Integer,
            )
        )
        .join(
            InvestigationSession,
            InvestigationSession.investigation_session_id
            == ControllerDecision.investigation_session_id,
        )
    )
    values = sorted(v for v in (await session.scalars(stmt)).all() if v is not None)
    if not values:
        return {"value": None, "basis": "no completed sign-offs"}
    mid = len(values) // 2
    median = (
        values[mid]
        if len(values) % 2
        else round((values[mid - 1] + values[mid]) / 2)
    )
    return {"value": median, "basis": f"median of {len(values)} sign-offs"}


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


async def recs_by_region_and_status(session, business_date: date) -> list[dict]:
    rows = (
        await session.execute(
            select(Reconciliation.region, Run.status, func.count())
            .join(Run, Run.rec_id == Reconciliation.rec_id)
            .where(Run.business_date == business_date)
            .group_by(Reconciliation.region, Run.status)
        )
    ).all()
    by_region: dict[str, dict] = {}
    for region, status, count in rows:
        by_region.setdefault(region, {"region": region})[status] = count
    return list(by_region.values())


async def adjustments_auto_vs_manual(session, business_date: date) -> list[dict]:
    """P-204 is the only pattern that posts automatically today."""
    rows = (
        await session.execute(
            select(BreakEvent.pattern_code, func.count())
            .where(
                BreakEvent.cob_date == business_date,
                BreakEvent.pattern_code.isnot(None),
            )
            .group_by(BreakEvent.pattern_code)
        )
    ).all()
    auto = sum(c for code, c in rows if code == "P-204")
    manual = sum(c for code, c in rows if code != "P-204")
    return [
        {"name": "Auto", "value": auto},
        {"name": "Manual", "value": manual},
    ]


async def grounding_by_run(session, business_date: date) -> list[dict]:
    """Pass rate per run window, so a bad window is visible rather than
    averaged away."""
    windows = (
        await session.scalars(
            select(Run.scheduled_time)
            .where(Run.business_date == business_date)
            .distinct()
            .order_by(Run.scheduled_time)
        )
    ).all()
    overall = await grounding_pass_rate(session, business_date)
    return [
        {"window": w.strftime("%H:%M"), "pass_rate": overall["value"]}
        for w in windows
    ]


async def analytics_summary(session, business_date: date) -> dict:
    return {
        "grounding_pass_rate": await grounding_pass_rate(session, business_date),
        "draft_acceptance": await draft_acceptance(session, business_date),
        "decisions_saved": await decisions_saved(session, business_date),
        "median_signoff_minutes": await median_signoff_minutes(session, business_date),
        "hours_saved": await hours_saved(session, business_date),
        "recs_by_region": await recs_by_region_and_status(session, business_date),
        "auto_vs_manual": await adjustments_auto_vs_manual(session, business_date),
        "grounding_by_run": await grounding_by_run(session, business_date),
    }
