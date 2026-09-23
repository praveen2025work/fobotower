"""Loads the playbook YAML, validates it, and writes it into the graph.

The YAML file is the source of truth and lives in git, so its history is
the playbook's history. Each finding the orchestrator produces is stamped
with the playbook version that produced it, which is what lets an audit say
which rules were in force for a given decision.
"""

import os
from pathlib import Path

import yaml
from sqlalchemy import delete, select

from app.db.models_graph import Edge, Node
from app.playbook.schema import Playbook

ONTOLOGY_ENTITY = "ONTOLOGY"
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = REPO_ROOT / "config" / "playbook" / "fobo-cats-vs-motif.yaml"


def playbook_path() -> Path:
    return Path(os.getenv("FOBO_PLAYBOOK_PATH", DEFAULT_PATH))


def read_playbook(path: Path | None = None) -> Playbook:
    """Parse and validate. Raises with every problem listed, not just the first."""
    source = path or playbook_path()
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    return Playbook.model_validate(raw)


def _node(node_id, node_type, key, since, attrs=None) -> Node:
    return Node(node_id=node_id, node_type=node_type, natural_key=key,
                legal_entity_id=ONTOLOGY_ENTITY, attrs=attrs or {}, valid_from=since)


def _edge(edge_id, src, dst, edge_type, since, attrs=None) -> Edge:
    return Edge(edge_id=edge_id, from_node_id=src, to_node_id=dst,
                edge_type=edge_type, attrs=attrs or {}, valid_from=since)


ONTOLOGY_NODE_PREFIXES = ("component:", "category:", "verdict:", "finding:",
                          "test:", "evidence:", "policy:", "team:", "playbook:")


async def _clear(session) -> None:
    ids = select(Node.node_id).where(Node.legal_entity_id == ONTOLOGY_ENTITY)
    await session.execute(delete(Edge).where(Edge.from_node_id.in_(ids)))
    await session.execute(delete(Edge).where(Edge.to_node_id.in_(ids)))
    await session.execute(delete(Node).where(Node.legal_entity_id == ONTOLOGY_ENTITY))


async def load_playbook(session, playbook: Playbook | None = None, *,
                        commit: bool = True) -> Playbook:
    pb = playbook or read_playbook()
    since = pb.effective_from
    await _clear(session)

    session.add(_node("playbook:current", "Playbook", pb.version, since,
                      {"version": pb.version, "source": pb.source,
                       "effective_from": str(since)}))
    for side, names in pb.components.items():
        for name in names:
            session.add(_node(f"component:{side}:{name}", "Component", name, since, {"side": side}))
    for code, c in pb.categories.items():
        session.add(_node(f"category:{code}", "Category", code, since,
                          {"label": c.name, "determinism": c.determinism}))
    for verdict in ("POST", "DO_NOT_POST", "ESCALATE", "CORRECT_AND_REPOST"):
        session.add(_node(f"verdict:{verdict}", "Verdict", verdict, since))
    for team in pb.teams:
        session.add(_node(f"team:{team}", "Team", team, since))
    for param, p in pb.policy.items():
        # value may be None: that is how P1 knows a threshold is unset.
        session.add(_node(f"policy:{param}", "Policy", param, since,
                          {"value": p.value, "unit": p.unit, "used_by": p.used_by,
                           "owner": "Product Control"}))
    for tid, t in pb.tests.items():
        session.add(_node(f"test:{tid}", "Test", tid, since,
                          {"side": t.side, "checks": t.checks, "component": t.validates,
                           "on_fail": t.on_fail}))
    for name in {e for t in pb.tests.values() for e in t.evidence}:
        session.add(_node(f"evidence:{name}", "EvidenceType", name, since))
    for code, f in pb.findings.items():
        session.add(_node(f"finding:{f.test}:{code}", "Finding", code, since,
                          {"description": f.description, "side": f.side}))
    await session.flush()

    for tid, t in pb.tests.items():
        session.add(_edge(f"e:{tid}:validates", f"test:{tid}",
                          f"component:{t.side}:{t.validates}", "VALIDATES", since))
        for dep in t.requires_on_fail:
            session.add(_edge(f"e:{tid}:requires:{dep}", f"test:{tid}", f"test:{dep}",
                              "ON_FAIL_REQUIRES", since))
        for ev in t.evidence:
            session.add(_edge(f"e:{tid}:evidence:{ev}", f"test:{tid}", f"evidence:{ev}",
                              "REQUIRES_EVIDENCE", since))
        for p in t.policy:
            session.add(_edge(f"e:{tid}:policy:{p}", f"test:{tid}", f"policy:{p}",
                              "DEPENDS_ON_POLICY", since))
    for code, f in pb.findings.items():
        session.add(_edge(f"e:{f.test}:finding:{code}", f"test:{f.test}",
                          f"finding:{f.test}:{code}", "HAS_FINDING", since))
        if f.indicates:
            session.add(_edge(f"e:finding:{code}:cat", f"finding:{f.test}:{code}",
                              f"category:{f.indicates}", "INDICATES", since))
    for code, by_side in pb.default_verdicts.items():
        for side, verdict in by_side.items():
            session.add(_edge(f"e:cat:{code}:{side}:verdict", f"category:{code}",
                              f"verdict:{verdict}", "DEFAULT_VERDICT", since,
                              {"when_side": side}))
    for code, c in pb.categories.items():
        session.add(_edge(f"e:cat:{code}:route", f"category:{code}",
                          f"team:{c.escalate_to}", "ROUTES_TO", since))

    if commit:
        await session.commit()
    return pb


async def loaded_version(session) -> str | None:
    node = await session.scalar(select(Node).where(Node.node_id == "playbook:current"))
    return node.natural_key if node else None
