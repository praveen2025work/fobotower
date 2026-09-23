from datetime import date

from sqlalchemy import select

from app.db.base import get_session
from app.db.models_graph import Edge, Node
from app.graph.ontology import OntologyRepository
from fixtures.ontology import load_ontology

AS_OF = date(2026, 8, 3)


async def _repo(s):
    await load_ontology(s)
    return OntologyRepository(s)


async def test_fo3_failure_requires_fo6_before_concluding():
    """The skill: FO-3 failing means 'go to FO-6 before concluding'.
    A pull factor move is not a root cause until the redemption analysis
    says whether CATS calculated it."""
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.required_on_fail("FO-3", AS_OF) == ["FO-6"]


async def test_a_test_with_no_dependency_requires_nothing():
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.required_on_fail("FO-1", AS_OF) == []


async def test_fo7_cannot_conclude_without_corporate_action_evidence():
    """Price = 0 may be a valid corporate action. FO-7 can never resolve on
    the price alone."""
    async with get_session() as s:
        repo = await _repo(s)
        needed = await repo.evidence_required("FO-7", AS_OF)
        assert "Corporate action file" in needed
        assert "Bond metadata" in needed


async def test_fo_and_bo_tests_are_separated_by_side():
    async with get_session() as s:
        repo = await _repo(s)
        fo = [t["test_id"] for t in await repo.tests_for_side("FO", AS_OF)]
        bo = [t["test_id"] for t in await repo.tests_for_side("BO", AS_OF)]
        assert fo == [f"FO-{i}" for i in range(1, 9)]
        assert bo == [f"BO-{i}" for i in range(1, 7)]


async def test_fo6_finding_a_indicates_a_redemption_break():
    """Appendix A: pull factor event missing -> Category C."""
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.finding_category("A", AS_OF) == "C"


async def test_a_fo_side_cause_never_defaults_to_posting():
    """R2 and Appendix A. Posting a FOBO adjustment against an FO cause
    masks the upstream failure and needs a later reversal."""
    async with get_session() as s:
        repo = await _repo(s)
        for category in "ABCDEF":
            assert await repo.default_verdict(category, "FO", AS_OF) == "DO_NOT_POST"


async def test_a_bo_side_cause_in_a_codified_category_defaults_to_posting():
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.default_verdict("C", "BO", AS_OF) == "POST"


async def test_judgement_categories_escalate_regardless_of_side():
    async with get_session() as s:
        repo = await _repo(s)
        for side in ("FO", "BO"):
            assert await repo.default_verdict("G", side, AS_OF) == "ESCALATE"
            assert await repo.default_verdict("H", side, AS_OF) == "ESCALATE"


async def test_an_unknown_side_gets_no_default_rather_than_a_guess():
    """A missing rule is an escalation, not a POST."""
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.default_verdict("C", "UNKNOWN", AS_OF) is None


async def test_redemption_breaks_route_to_cats_support():
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.escalation_route("C", AS_OF) == "CATS support"


async def test_every_policy_parameter_starts_unset():
    """Rule P1: until Product Control supplies a value, it is unknown."""
    async with get_session() as s:
        repo = await _repo(s)
        params = ["materiality_threshold", "calculation_reasonable_tolerance"]
        assert await repo.unset_policies(params, AS_OF) == params


async def test_a_policy_with_a_value_is_not_reported_unset():
    async with get_session() as s:
        repo = await _repo(s)
        node = await s.scalar(
            select(Node).where(Node.node_id == "policy:materiality_threshold")
        )
        node.attrs = {**node.attrs, "value": 10000}
        await s.commit()
        assert await repo.unset_policies(["materiality_threshold"], AS_OF) == []


async def test_a_missing_policy_row_counts_as_unset():
    """Absence of a policy is not permission to assume one."""
    async with get_session() as s:
        repo = await _repo(s)
        assert await repo.unset_policies(["no_such_param"], AS_OF) == ["no_such_param"]


async def test_a_playbook_change_is_visible_only_from_its_effective_date():
    """Bitemporal: an audit must see the rule in force at decision time,
    not today's rule."""
    async with get_session() as s:
        repo = await _repo(s)
        # Product Control closes the FO-3 -> FO-6 rule and it stops applying.
        edge = await s.scalar(select(Edge).where(Edge.edge_id == "e:FO-3:requires:FO-6"))
        edge.valid_to = date(2026, 8, 31)
        await s.commit()

        assert await repo.required_on_fail("FO-3", date(2026, 8, 3)) == ["FO-6"]
        assert await repo.required_on_fail("FO-3", date(2026, 9, 15)) == []
