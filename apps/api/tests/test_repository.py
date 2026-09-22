from datetime import date

import pytest

from app.contracts.models import Caller
from app.db.base import get_session
from app.graph.errors import UnresolvedBook
from app.graph.repository import GraphRepository
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
OUTSIDER = Caller(
    staff_id="p2", roles=["FO"], entity_scope=["LE-EMEA-01"], region="EMEA"
)


async def test_resolves_a_book():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        got = await repo.resolve_book("APAC-CASH-01", date(2026, 8, 3), FO)
        assert got == "book:APAC-CASH-01"


async def test_unknown_book_raises_rather_than_guessing():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        with pytest.raises(UnresolvedBook):
            await repo.resolve_book("NOPE-01", date(2026, 8, 3), FO)


async def test_a_caller_outside_the_entity_scope_cannot_resolve():
    """Entitlement is enforced in the query, so this is indistinguishable
    from the book not existing. That indistinguishability is the point:
    post-filtering leaks through counts and timing."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        with pytest.raises(UnresolvedBook):
            await repo.resolve_book("APAC-CASH-01", date(2026, 8, 3), OUTSIDER)


async def test_as_of_returns_the_hierarchy_in_force_on_that_date():
    """APAC-CASH-05 moved from APAC-TREASURY to APAC-CASH on 2026-07-01."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        before = await repo.book_context("book:APAC-CASH-05", date(2026, 6, 15), FO)
        after = await repo.book_context("book:APAC-CASH-05", date(2026, 8, 3), FO)
        assert before["desk"] == "APAC-TREASURY"
        assert after["desk"] == "APAC-CASH"


async def test_lineage_is_entitlement_filtered_and_depth_bounded():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        visible = await repo.lineage(
            "book:APAC-CASH-01", "BELONGS_TO", 4, date(2026, 8, 3), FO
        )
        assert [n["natural_key"] for n in visible] == ["APAC-CASH"]

        blocked = await repo.lineage(
            "book:APAC-CASH-01", "BELONGS_TO", 4, date(2026, 8, 3), OUTSIDER
        )
        assert blocked == []


async def test_similar_breaks_returns_priors_for_that_book_only():
    """book_id is a filter, not decoration: the spec indexes on
    (book_id, line_code, cob_date) precisely so this query is cheap."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        priors = await repo.similar_breaks(
            "book:APAC-CASH-01", "CASH", date(2026, 8, 3), 180, FO
        )
        assert len(priors) > 0
        assert all(p["pattern_code"] == "P-204" for p in priors)
        assert all(p["book_id"] == "book:APAC-CASH-01" for p in priors)


async def test_similar_breaks_excludes_the_current_cob_date():
    """Today's unresolved breaks are not priors."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        priors = await repo.similar_breaks(
            "book:APAC-CASH-01", "CASH", date(2026, 8, 3), 180, FO
        )
        assert all(p["cob_date"] < date(2026, 8, 3) for p in priors)


async def test_similar_breaks_respects_the_lookback_window():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        # Priors sit on 2026-06-01; a 10-day lookback from COB excludes them.
        priors = await repo.similar_breaks(
            "book:APAC-CASH-01", "CASH", date(2026, 8, 3), 10, FO
        )
        assert priors == []


async def test_the_union_of_per_book_priors_is_the_full_history():
    """Every one of the 42 priors belongs to exactly one book, so querying
    each book and deduplicating recovers the whole history. The group node
    depends on this to derive the 88% rate."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        seen = {}
        for i in range(1, 13):
            for p in await repo.similar_breaks(
                f"book:APAC-CASH-{i:02d}", "CASH", date(2026, 8, 3), 180, FO
            ):
                seen[p["break_id"]] = p
        assert len(seen) == 42
