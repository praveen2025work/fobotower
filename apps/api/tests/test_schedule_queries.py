from app.db.base import get_session
from app.queries.schedule import header_stats, regions_with_recs, run_windows
from fixtures.history import COB, load_history
from fixtures.loader import load_all


async def _seeded(s):
    await load_all(s)
    await load_history(s)


async def test_run_windows_come_from_the_runs_not_a_constant():
    async with get_session() as s:
        await _seeded(s)
        assert await run_windows(s, COB) == ["11:00", "15:00", "17:00", "19:00"]


async def test_regions_are_ordered_apac_emea_amer():
    async with get_session() as s:
        await _seeded(s)
        regions = await regions_with_recs(s, COB)
        assert [r["region"] for r in regions] == ["APAC", "EMEA", "AMER"]


async def test_a_rec_carries_its_scheduled_and_completed_times():
    async with get_session() as s:
        await _seeded(s)
        regions = await regions_with_recs(s, COB)
        apac = next(r for r in regions if r["region"] == "APAC")["recs"]
        r1055 = next(r for r in apac if r["rec_id"] == "R-1055")
        assert r1055["scheduled"] == "11:00"
        assert r1055["completed"] == "11:52"
        assert r1055["status"] == "awaiting"
        assert r1055["books_open"] == 12
        assert r1055["books_total"] == 14


async def test_a_scheduled_rec_has_no_completion_time():
    async with get_session() as s:
        await _seeded(s)
        regions = await regions_with_recs(s, COB)
        apac = next(r for r in regions if r["region"] == "APAC")["recs"]
        assert next(r for r in apac if r["rec_id"] == "R-1061")["completed"] is None


async def test_pending_adjustments_are_counted_before_any_case_is_opened():
    """The mock shows '14 adj. pending' on load. Counting through
    investigation_session would report 0 until someone clicks."""
    async with get_session() as s:
        await _seeded(s)
        regions = await regions_with_recs(s, COB)
        apac = next(r for r in regions if r["region"] == "APAC")["recs"]
        assert next(r for r in apac if r["rec_id"] == "R-1055")["adj_pending"] == 14


async def test_header_status_counts_match_the_mock():
    async with get_session() as s:
        await _seeded(s)
        st = await header_stats(s, COB)
        assert st["recs"] == 7
        assert st["cleared"] == 2
        assert st["awaiting"] == 1
        assert st["blocked"] == 1
        # 14 on R-1055, 8 on R-2031, 1 on R-2048.
        assert st["adj_pending"] == 23


async def test_header_book_counts_match_the_mock():
    async with get_session() as s:
        await _seeded(s)
        st = await header_stats(s, COB)
        # 160 master books across the seven recs; 72 not yet open.
        assert st["books_open"] == 88
        assert st["books_not_open"] == 72


async def test_the_clock_is_derived_not_declared():
    """'now' is the last recorded activity; 'next' is the earliest window
    still scheduled after it."""
    async with get_session() as s:
        await _seeded(s)
        st = await header_stats(s, COB)
        assert st["now"] == "17:22"
        assert st["next_run"] == "19:00"


async def test_unlocked_counts_books_with_no_open_breaks():
    async with get_session() as s:
        await _seeded(s)
        st = await header_stats(s, COB)
        # Resolved: 12 history books, plus the 3 Rates and 3 Cash books whose
        # breaks cleared today. Open: 12 Prime, 8 FI Credit, 1 Collateral.
        assert st["unlocked"] == 18
        assert st["unlocked_total"] == 39


async def test_each_open_rec_reports_its_own_pending_count():
    """Switching recs must show that rec's work, so the counts have to be
    per-rec rather than a single total spread over all of them."""
    async with get_session() as s:
        await _seeded(s)
        per_rec = {
            rec["rec_id"]: rec["adj_pending"]
            for region in await regions_with_recs(s, COB)
            for rec in region["recs"]
        }
        assert per_rec["R-1055"] == 14
        assert per_rec["R-2031"] == 8
        assert per_rec["R-2048"] == 1
        assert per_rec["R-1042"] == 0
