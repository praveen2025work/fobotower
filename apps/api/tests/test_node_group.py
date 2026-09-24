from datetime import date

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.resolve import resolve
from app.workflow.session import ensure_investigation_session
from fixtures.loader import read_breaks

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")

# Each fixture break names the cause it should trigger; this maps that cause
# to the snapshot fields that make the corresponding check fire.
CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}


def breaks_with_causes():
    return [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in read_breaks()]


async def _run_to_group(session, breaks=None):
    st = {
        "investigation_session_id": "sess-1",
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": FO,
        "breaks": breaks if breaks is not None else breaks_with_causes(),
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }
    await ensure_investigation_session(session, st)
    st |= await resolve(st, session=session)
    st |= await gather(st, session=session)
    st |= await group(st, session=session)
    return st


async def test_fourteen_breaks_collapse_to_four_groups():
    """This is the 'decisions saved' lever. If this fails, the metric is a lie."""
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        st = await _run_to_group(s)
        assert len(st["pattern_groups"]) == 4


async def test_group_sizes_match_the_mock():
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        st = await _run_to_group(s)
        sizes = {g.pattern_code: len(g.break_ids) for g in st["pattern_groups"]}
        assert sizes == {"P-204": 6, "CPTY-REF": 3, "LATE-BOOK": 3, "DUP-SETTLE": 2}


async def test_p204_is_auto_and_the_rest_are_manual():
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        st = await _run_to_group(s)
        modes = {g.pattern_code: g.mode for g in st["pattern_groups"]}
        assert modes["P-204"] == "auto"
        assert all(m == "manual" for c, m in modes.items() if c != "P-204")


async def test_p204_carries_the_historical_approval_rate():
    """Derived from the 42 priors, not hard-coded. Books appear more than
    once across the population, so the rate must deduplicate priors by
    break_id or it drifts off 0.88."""
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        st = await _run_to_group(s)
        p204 = next(g for g in st["pattern_groups"] if g.pattern_code == "P-204")
        assert p204.historical_approval_rate == 0.88


async def test_every_break_lands_in_exactly_one_group():
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        st = await _run_to_group(s)
        assigned = [b for g in st["pattern_groups"] for b in g.break_ids]
        assert len(assigned) == 14
        assert len(set(assigned)) == 14


async def test_a_break_with_no_positive_cause_is_grouped_as_ungrouped():
    """It is never silently dropped."""
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        clean = [
            {
                "break_id": "b-clean",
                "book_ref": "PRIME-MB-01",
                "line_code": "CASH",
                "fo_value": 100000.0,
                "bo_value": 99000.0,
                "cause": "C1",
            }
        ]
        st = await _run_to_group(s, breaks=clean)
        assert [g.pattern_code for g in st["pattern_groups"]] == ["UNGROUPED"]
        assert st["pattern_groups"][0].break_ids == ["b-clean"]


async def test_grouping_is_deterministic():
    async with get_session() as s:
        from fixtures.loader import load_all

        await load_all(s)
        a = await _run_to_group(s)
        b = await _run_to_group(s)
        assert [g.model_dump() for g in a["pattern_groups"]] == [
            g.model_dump() for g in b["pattern_groups"]
        ]
