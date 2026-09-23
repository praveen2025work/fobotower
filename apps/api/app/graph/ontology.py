"""Reads Layer A (investigation ontology) and Layer B (policy).

Not entity-scoped: the playbook is shared reference knowledge, not position
data, so the entitlement predicate that guards instance reads does not apply.
It is still read as_of a date — "which rule was in force when this decision
was made" is exactly the question an audit asks.

Workflow nodes ask this module what to do next. They never hardcode it,
which is what lets Product Control change the playbook without a redeploy.
"""

from datetime import date

from sqlalchemy import and_, or_, select

from app.db.models_graph import Edge, Node


def _valid_at(model, as_of: date):
    return and_(
        model.valid_from <= as_of,
        or_(model.valid_to.is_(None), model.valid_to >= as_of),
    )


class OntologyRepository:
    def __init__(self, session):
        self._s = session

    async def _targets(self, source_id: str, edge_type: str, as_of: date) -> list:
        rows = (
            await self._s.execute(
                select(Node, Edge)
                .join(Edge, Edge.to_node_id == Node.node_id)
                .where(
                    Edge.from_node_id == source_id,
                    Edge.edge_type == edge_type,
                    _valid_at(Edge, as_of),
                    _valid_at(Node, as_of),
                )
                .order_by(Node.natural_key)
            )
        ).all()
        return rows

    async def required_on_fail(self, test_id: str, as_of: date) -> list[str]:
        """Tests that must run before a failing test may conclude.

        FO-3 failing requires FO-6: a pull factor move is not a root cause
        until the redemption analysis says whether CATS calculated it.
        """
        rows = await self._targets(f"test:{test_id}", "ON_FAIL_REQUIRES", as_of)
        return [node.natural_key for node, _edge in rows]

    async def evidence_required(self, test_id: str, as_of: date) -> list[str]:
        rows = await self._targets(f"test:{test_id}", "REQUIRES_EVIDENCE", as_of)
        return [node.natural_key for node, _edge in rows]

    async def tests_for_side(self, side: str, as_of: date) -> list[dict]:
        rows = (
            await self._s.scalars(
                select(Node)
                .where(Node.node_type == "Test", _valid_at(Node, as_of))
                .order_by(Node.natural_key)
            )
        ).all()
        return [
            {"test_id": n.natural_key, **n.attrs}
            for n in rows
            if n.attrs.get("side") == side
        ]

    async def finding_category(self, finding_code: str, as_of: date) -> str | None:
        rows = await self._targets(f"finding:FO-6:{finding_code}", "INDICATES", as_of)
        return rows[0][0].natural_key if rows else None

    async def category(self, code: str, as_of: date) -> dict | None:
        node = await self._s.scalar(
            select(Node).where(
                Node.node_id == f"category:{code}", _valid_at(Node, as_of)
            )
        )
        return {"code": code, **node.attrs} if node else None

    async def default_verdict(self, category: str, side: str, as_of: date) -> str | None:
        """The verdict the playbook prescribes for a category and side.

        Returns None when the playbook is silent, rather than a default —
        a missing rule is an escalation, not a POST.
        """
        rows = await self._targets(f"category:{category}", "DEFAULT_VERDICT", as_of)
        for node, edge in rows:
            if edge.attrs.get("when_side") == side:
                return node.natural_key
        return None

    async def escalation_route(self, category: str, as_of: date) -> str | None:
        rows = await self._targets(f"category:{category}", "ROUTES_TO", as_of)
        return rows[0][0].natural_key if rows else None

    async def policy(self, param: str, as_of: date) -> dict | None:
        node = await self._s.scalar(
            select(Node).where(
                Node.node_id == f"policy:{param}", _valid_at(Node, as_of)
            )
        )
        return {"param": param, **node.attrs} if node else None

    async def unset_policies(self, params: list[str], as_of: date) -> list[str]:
        """Rule P1: which of these parameters has no value in force.

        A parameter missing entirely counts as unset too — absence of a
        policy row is not permission to assume one.
        """
        unset = []
        for param in params:
            p = await self.policy(param, as_of)
            if p is None or p.get("value") is None:
                unset.append(param)
        return unset
