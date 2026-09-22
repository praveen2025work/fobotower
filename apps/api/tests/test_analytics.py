from app.db.base import get_session
from app.queries.analytics import (
    MANUAL_MINUTES_PER_DECISION,
    analytics_summary,
    decisions_saved,
    draft_acceptance,
    hours_saved,
)
from fixtures.history import COB, load_history
from fixtures.loader import load_all


async def _seeded(s):
    await load_all(s)
    await load_history(s)


async def test_every_tile_reports_its_basis():
    """A figure with no stated basis is a number nobody can check."""
    async with get_session() as s:
        await _seeded(s)
        summary = await analytics_summary(s, COB)
        for key in (
            "grounding_pass_rate",
            "draft_acceptance",
            "median_signoff_minutes",
            "hours_saved",
            "decisions_saved",
        ):
            assert summary[key].get("basis"), f"{key} has no basis"


async def test_decisions_saved_counts_breaks_against_patterns():
    async with get_session() as s:
        await _seeded(s)
        saved = await decisions_saved(s, COB)
        assert saved["from"] > saved["to"] > 0


async def test_hours_saved_follows_from_decisions_avoided():
    async with get_session() as s:
        await _seeded(s)
        saved = await decisions_saved(s, COB)
        hours = await hours_saved(s, COB)
        avoided = saved["from"] - saved["to"]
        assert hours["value"] == round(
            avoided * MANUAL_MINUTES_PER_DECISION / 60, 1
        )
        assert str(MANUAL_MINUTES_PER_DECISION) in hours["basis"]


async def test_draft_acceptance_is_derived_from_decisions():
    async with get_session() as s:
        await _seeded(s)
        acc = await draft_acceptance(s, COB)
        assert acc["value"] is not None
        assert 0 <= acc["value"] <= 100


async def test_a_metric_with_no_data_returns_none_rather_than_zero():
    """Zero and 'unknown' are different answers."""
    async with get_session() as s:
        acc = await draft_acceptance(s, COB)
        assert acc["value"] is None
        assert "no decisions" in acc["basis"]


async def test_auto_versus_manual_splits_the_population():
    async with get_session() as s:
        await _seeded(s)
        split = await adjust(s)
        assert sum(x["value"] for x in split) > 0


async def adjust(s):
    from app.queries.analytics import adjustments_auto_vs_manual

    return await adjustments_auto_vs_manual(s, COB)


async def test_recs_by_region_covers_every_region():
    async with get_session() as s:
        await _seeded(s)
        rows = (await analytics_summary(s, COB))["recs_by_region"]
        assert {r["region"] for r in rows} == {"APAC", "EMEA", "AMER"}


async def test_median_signoff_is_a_positive_duration():
    """A historical session whose created_ts defaults to now() yields a
    negative duration — the figure reads as nonsense on the tile."""
    async with get_session() as s:
        await _seeded(s)
        from app.queries.analytics import median_signoff_minutes

        m = await median_signoff_minutes(s, COB)
        assert m["value"] is not None
        assert m["value"] > 0, f"negative sign-off duration: {m['value']}"
        assert m["value"] < 24 * 60, "a sign-off should not take over a day"
