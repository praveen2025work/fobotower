from app.db.base import get_session
from app.queries.activity import activity_feed
from fixtures.history import COB, load_history
from fixtures.loader import load_all


async def _seeded(s):
    await load_all(s)
    await load_history(s)


async def test_feed_is_newest_first():
    async with get_session() as s:
        await _seeded(s)
        feed = await activity_feed(s, COB)
        times = [e["at"] for e in feed]
        assert times == sorted(times, reverse=True)


async def test_a_cleared_run_emits_notified_unlocked_and_cleared():
    async with get_session() as s:
        await _seeded(s)
        feed = await activity_feed(s, COB)
        kinds = [e["kind"] for e in feed]
        for kind in ("notified", "unlocked", "cleared"):
            assert kind in kinds, f"no {kind} event"


async def test_a_blocked_run_says_why():
    async with get_session() as s:
        await _seeded(s)
        feed = await activity_feed(s, COB)
        blocked = [e for e in feed if e["kind"] == "blocked"]
        assert blocked
        assert "source-system correction required" in blocked[0]["text"]


async def test_unlock_events_carry_a_real_book_count():
    """The mock shows '19 books' and '34 books' — those are run totals,
    not decoration."""
    async with get_session() as s:
        await _seeded(s)
        feed = await activity_feed(s, COB)
        unlocked = [e for e in feed if e["kind"] == "unlocked"]
        assert unlocked
        assert any(str(n) in e["text"] for e in unlocked for n in (22, 13))


async def test_every_event_carries_a_tone_the_ui_can_colour():
    async with get_session() as s:
        await _seeded(s)
        for e in await activity_feed(s, COB):
            assert e["tone"] in {"green", "blue", "red", "amber"}
