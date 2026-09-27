from fobo.db.base import get_session
from fobo.reports.hours_saved import MANUAL_MINUTES_PER_DECISION, decisions_saved, hours_saved
from seed_data.history import COB, load_history
from seed_data.loader import load_all


async def _seeded(s):
    await load_all(s)
    await load_history(s)


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
