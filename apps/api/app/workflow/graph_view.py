"""The compiled workflow graph and its decision logic, derived from code.

Nothing here is hand-typed. The graph comes from build_graph(...).get_graph()
— the same call the running workflow compiles from — the escalation and
pattern/guard lists live next to the code that applies them (registry.py,
determinism.py, guards.py), and defined_in() points at wherever a piece is
actually defined. The Workflow tab renders this; it invents nothing itself.
"""

import inspect
from pathlib import Path

from langchain_core.runnables.graph import Edge

from app.playbook.loader import read_playbook
from app.reasoning.determinism import PATTERN_ORDER, classify
from app.reasoning.guards import GUARD_RULES, guard_verdict
from app.workflow.config import REPO_ROOT, WorkflowConfig
from app.workflow.graph import _router, build_graph
from app.workflow.nodes.escalate import REASONS, escalate
from app.workflow.registry import STEPS

ROUTER_RULE = (
    "After a step that can escalate: if the step set outcome = escalated the "
    "run goes to Escalate and ends; otherwise it continues to the next "
    "configured step."
)


def defined_in(obj: object) -> str:
    """Repo-relative "path · qualified name" for wherever `obj` is defined.

    Computed from the object itself (inspect.getsourcefile / __qualname__),
    never hand-typed, so this cannot point at a path the code has moved away
    from.
    """
    source_file = inspect.getsourcefile(obj) or inspect.getfile(obj)
    path = Path(source_file).resolve()
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        rel = path
    name = getattr(obj, "__qualname__", getattr(obj, "__name__", str(obj)))
    return f"{rel} · {name}"


def _node_view(node_id: str, cfg: WorkflowConfig) -> dict:
    if node_id == "__start__":
        kind, label = "start", "Start"
    elif node_id == "__end__":
        kind, label = "end", "End"
    elif node_id == "escalate":
        kind, label = "escalate", "Escalate"
    else:
        kind, label = "step", STEPS[node_id].label
    view = {"id": node_id, "kind": kind, "label": label}
    if kind == "step":
        view["decided_by"] = STEPS[node_id].decided_by
    view["paused_before"] = node_id in cfg.pause_before
    return view


def _edge_view(edge: Edge, position: dict[str, int]) -> dict:
    base = {"source": edge.source, "target": edge.target,
            "conditional": bool(edge.conditional)}
    if edge.conditional and edge.target == "escalate":
        step = STEPS.get(edge.source)
        reasons = [code for code, _when in step.escalates_when] if step else []
        return base | {"label": "if escalated", "reasons": reasons}
    if edge.conditional:
        return base | {"label": "otherwise"}
    return base | {"label": None}


def _logic(cfg: WorkflowConfig) -> dict:
    logic: dict[str, dict] = {}
    for name in cfg.steps:
        step = STEPS[name]
        logic[name] = {
            "escalates_when": [{"code": c, "when": w} for c, w in step.escalates_when],
            "defined_in": defined_in(step.fn),
        }
    logic["escalate"] = {"reasons": sorted(REASONS), "defined_in": defined_in(escalate)}
    return logic


def _decision(cfg: WorkflowConfig) -> dict:
    pb = read_playbook()
    cause_checks = [
        {
            "check": check,
            "category": c.category,
            "category_name": pb.categories[c.category].name,
            "side": c.side,
            "reason": c.reason,
        }
        for check, c in sorted(pb.cause_checks.items())
    ]
    default_verdicts = [
        {
            "category": code,
            "category_name": pb.categories[code].name,
            "FO": by_side["FO"],
            "BO": by_side["BO"],
        }
        for code, by_side in sorted(pb.default_verdicts.items())
    ]
    return {
        "defined_in": [defined_in(classify), defined_in(guard_verdict)],
        "patterns": [{"code": c, "meaning": m} for c, m in PATTERN_ORDER],
        "cause_checks": cause_checks,
        "default_verdicts": default_verdicts,
        "reasoner": cfg.settings.reason.reasoner,
        "guards": [{"id": rid, "rule": rule} for rid, rule in GUARD_RULES],
    }


def graph_view(cfg: WorkflowConfig, number: int) -> dict:
    """The graph as it is actually compiled for `cfg`, plus why it routes the
    way it does. Pure: no database access, so it can be built for any
    version's config, active or historical."""
    graph = build_graph(None, config=cfg).get_graph()
    position = {node_id: i for i, node_id in enumerate(graph.nodes)}
    nodes = [_node_view(node_id, cfg) for node_id in graph.nodes]
    edges = [
        _edge_view(e, position)
        for e in sorted(graph.edges, key=lambda e: (position[e.source], e.target))
    ]
    return {
        "version": number,
        "nodes": nodes,
        "edges": edges,
        "pause_before": list(cfg.pause_before),
        "router": {"rule": ROUTER_RULE, "defined_in": defined_in(_router)},
        "logic": _logic(cfg),
        "decision": _decision(cfg),
    }
