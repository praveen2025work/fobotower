"""Layer A — the investigation ontology, and Layer B — policy parameters.

The skill's test/finding/category structure lives here as graph rows rather
than as Python constants, so Product Control can change the playbook without
a redeploy, and so there is one source of truth. Anything encoded here is
deleted from the skill prompt.

Loaded into the same bitemporal node/edge tables as the instance layer: an
ontology that cannot be read `as_of` a date cannot answer "which rule was in
force when this decision was made".
"""

from datetime import date

from sqlalchemy import delete, select

from app.db.models_graph import Edge, Node

ONTOLOGY_ENTITY = "ONTOLOGY"
ONTOLOGY_FROM = date(2020, 1, 1)

# (component, side)
COMPONENTS = [
    ("Position", "FO"), ("Price", "FO"), ("MTM", "FO"), ("Trading PnL", "FO"),
    ("Pull Factor", "FO"), ("Redemption Events", "FO"), ("Trade Economics", "FO"),
    ("Position", "BO"), ("Price", "BO"), ("Settlement", "BO"),
    # Not in the skill's BO decomposition map, but BO-3 validates it. The
    # map and the test table disagree in the source document; the test is
    # explicit, so the component is added here. Raised with Product Control.
    ("Pull Factor", "BO"),
    ("Cash Movement", "BO"), ("Accounting Entry", "BO"), ("Journal Generation", "BO"),
]

# test_id -> (side, validates component, what it checks)
TESTS = {
    "FO-1": ("FO", "Position", "Prior day close position = current day open position"),
    "FO-2": ("FO", "Price", "Yesterday close price = today open price"),
    "FO-3": ("FO", "Pull Factor", "Yesterday pull factor = today opening pull factor"),
    "FO-4": ("FO", "MTM", "Does Position x Price Movement explain MTM?"),
    "FO-5": ("FO", "Trading PnL", "Do trade economics explain Trading PnL?"),
    "FO-6": ("FO", "Redemption Events", "Redemption occurred? Factor changed? PnL expected? CATS calculated it?"),
    "FO-7": ("FO", "Price", "Price = 0 — valid corporate action or data quality issue?"),
    "FO-8": ("FO", "Price", "Holiday close = next business day open"),
    "BO-1": ("BO", "Position", "Position balance; position quantity; settlement activity"),
    "BO-2": ("BO", "Price", "Market price; accounting price; pricing source"),
    "BO-3": ("BO", "Pull Factor", "Factor used; redemption treatment; calculation logic"),
    "BO-4": ("BO", "Settlement", "Trade settled? Settlement date? Quantity? Cash?"),
    "BO-5": ("BO", "Cash Movement", "Redemption cash; coupon cash; settlement cash"),
    "BO-6": ("BO", "Journal Generation", "MOTIF entry generated? Journal posted? Rejected?"),
}

# A failing test that cannot conclude until another test has run.
# FO-3 must reach FO-6 before concluding — the skill is explicit.
ON_FAIL_REQUIRES = [("FO-3", "FO-6")]

# test -> evidence that must be on file before the test can conclude.
REQUIRES_EVIDENCE = {
    "FO-7": ["Corporate action file", "Trade file", "Bond metadata"],
    "FO-6": ["Corporate action file", "Pull factor history"],
    "FO-2": ["Pricing file"],
    "FO-1": ["Position file"],
    "BO-6": ["Journal status"],
}

# FO-6 findings A/B/C -> which side they implicate.
FINDINGS = {
    "A": ("Pull factor event missing; expected PnL exists, FO shows zero", "FO"),
    "B": ("Pull factor applied too early; artificial PnL generated", "FO"),
    "C": ("Redemption correctly reflected; proceed to BO validation", "NEITHER"),
}

# Skill §9 categories.
CATEGORIES = {
    "A": ("Price break", "deterministic"),
    "B": ("Pull factor break", "deterministic"),
    "C": ("Redemption break", "deterministic"),
    "D": ("Settlement break", "deterministic"),
    "E": ("Trade booking break", "deterministic"),
    "F": ("Data quality break", "deterministic"),
    "G": ("Corporate action break", "judgement"),
    "H": ("Novel break", "judgement"),
}

VERDICTS = ["POST", "DO_NOT_POST", "ESCALATE", "CORRECT_AND_REPOST"]

# Default verdict per category, conditional on which side the cause sits.
# A cause originating in FO never posts a FOBO adjustment — it would mask
# the upstream failure (skill §10 + Appendix A).
DEFAULT_VERDICTS = [
    ("A", "FO", "DO_NOT_POST"), ("A", "BO", "POST"),
    ("B", "FO", "DO_NOT_POST"), ("B", "BO", "POST"),
    ("C", "FO", "DO_NOT_POST"), ("C", "BO", "POST"),
    ("D", "FO", "DO_NOT_POST"), ("D", "BO", "POST"),
    ("E", "FO", "DO_NOT_POST"), ("E", "BO", "POST"),
    ("F", "FO", "DO_NOT_POST"), ("F", "BO", "DO_NOT_POST"),
    ("G", "FO", "ESCALATE"), ("G", "BO", "ESCALATE"),
    ("H", "FO", "ESCALATE"), ("H", "BO", "ESCALATE"),
]

# Skill §8 named scenarios that map straight to a verdict.
SCENARIO_VERDICTS = {
    "Posting failure": "CORRECT_AND_REPOST",
    "Static outlier": "DO_NOT_POST",
}

# Layer B — local parameters. value is null until Product Control supplies
# one; Rule P1 reads that null and refuses to invent a number.
POLICY_PARAMS = [
    ("materiality_threshold", "Step 1 — which breaks enter scope"),
    ("mtm_market_movement_tolerance", "FO-4"),
    ("calculation_reasonable_tolerance", "FO-6"),
    ("posting_policy_reference", "Section 10"),
    ("same_day_resolution_cutoff", "Section 10"),
]

ESCALATION_ROUTES = {
    "A": "Market data", "B": "CATS support", "C": "CATS support",
    "D": "Operations", "E": "Desk", "F": "Technology", "G": "Product Control",
    "H": "Product Control",
}


def _node(node_id: str, node_type: str, key: str, attrs: dict | None = None) -> Node:
    return Node(
        node_id=node_id, node_type=node_type, natural_key=key,
        legal_entity_id=ONTOLOGY_ENTITY, attrs=attrs or {},
        valid_from=ONTOLOGY_FROM,
    )


def _edge(edge_id: str, src: str, dst: str, edge_type: str,
          attrs: dict | None = None) -> Edge:
    return Edge(
        edge_id=edge_id, from_node_id=src, to_node_id=dst,
        edge_type=edge_type, attrs=attrs or {}, valid_from=ONTOLOGY_FROM,
    )


async def load_ontology(session, *, commit: bool = True) -> None:
    await _clear(session)

    for name, side in COMPONENTS:
        session.add(_node(f"component:{side}:{name}", "Component", name, {"side": side}))
    for code, (label, determinism) in CATEGORIES.items():
        session.add(_node(f"category:{code}", "Category", code,
                          {"label": label, "determinism": determinism}))
    for code in VERDICTS:
        session.add(_node(f"verdict:{code}", "Verdict", code))
    for code, (desc, side) in FINDINGS.items():
        session.add(_node(f"finding:FO-6:{code}", "Finding", code,
                          {"description": desc, "side": side}))
    for test_id, (side, component, checks) in TESTS.items():
        session.add(_node(f"test:{test_id}", "Test", test_id,
                          {"side": side, "checks": checks, "component": component}))
    for evidence in {e for lst in REQUIRES_EVIDENCE.values() for e in lst}:
        session.add(_node(f"evidence:{evidence}", "EvidenceType", evidence))
    for param, used_by in POLICY_PARAMS:
        # value is deliberately absent, not zero. P1 reads this.
        session.add(_node(f"policy:{param}", "Policy", param,
                          {"value": None, "used_by": used_by, "owner": "Product Control"}))
    for team in set(ESCALATION_ROUTES.values()):
        session.add(_node(f"team:{team}", "Team", team))
    await session.flush()

    for test_id, (side, component, _c) in TESTS.items():
        session.add(_edge(f"e:{test_id}:validates", f"test:{test_id}",
                          f"component:{side}:{component}", "VALIDATES"))
    for src, dst in ON_FAIL_REQUIRES:
        session.add(_edge(f"e:{src}:requires:{dst}", f"test:{src}",
                          f"test:{dst}", "ON_FAIL_REQUIRES"))
    for test_id, evidence_list in REQUIRES_EVIDENCE.items():
        for evidence in evidence_list:
            session.add(_edge(f"e:{test_id}:evidence:{evidence}", f"test:{test_id}",
                              f"evidence:{evidence}", "REQUIRES_EVIDENCE"))
    for code, (_d, side) in FINDINGS.items():
        session.add(_edge(f"e:FO-6:finding:{code}", "test:FO-6",
                          f"finding:FO-6:{code}", "HAS_FINDING"))
    session.add(_edge("e:finding:A:cat", "finding:FO-6:A", "category:C", "INDICATES"))
    session.add(_edge("e:finding:B:cat", "finding:FO-6:B", "category:B", "INDICATES"))
    for code, side, verdict in DEFAULT_VERDICTS:
        session.add(_edge(f"e:cat:{code}:{side}:verdict", f"category:{code}",
                          f"verdict:{verdict}", "DEFAULT_VERDICT", {"when_side": side}))
    for code, team in ESCALATION_ROUTES.items():
        session.add(_edge(f"e:cat:{code}:route", f"category:{code}",
                          f"team:{team}", "ROUTES_TO"))

    if commit:
        await session.commit()


async def _clear(session) -> None:
    await session.execute(delete(Edge).where(Edge.edge_id.like("e:%:validates")))
    for pattern in ("e:FO-%", "e:BO-%", "e:cat:%", "e:finding:%"):
        await session.execute(delete(Edge).where(Edge.edge_id.like(pattern)))
    for pattern in ("component:%", "category:%", "verdict:%", "finding:%",
                    "test:%", "evidence:%", "policy:%", "team:%"):
        await session.execute(delete(Node).where(Node.node_id.like(pattern)))


async def ontology_is_loaded(session) -> bool:
    return bool(
        await session.scalar(select(Node.node_id).where(Node.node_type == "Test").limit(1))
    )
