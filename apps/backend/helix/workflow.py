"""From a manifest's step list to a LangGraph run.

The registry declares what each core step needs and produces. A manifest's
order is checked against it before anything runs, and the three gates —
validate, review, record — can never be left out or reordered: no figure
reaches a person ungrounded, nothing is recorded without a person, and an
unrecorded decision never teaches the next run.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph

from helix import steps
from helix.db import checkpoint_dsn
from helix.observability import span
from helix.steps import ESCALATED, CaseState


@dataclass(frozen=True)
class Step:
    name: str
    fn: object
    label: str
    needs: frozenset[str]
    produces: frozenset[str]
    gate: bool = False


def _s(*names: str) -> frozenset[str]:
    return frozenset(names)


STEPS: dict[str, Step] = {s.name: s for s in [
    Step("load", steps.load, "Load items", _s("case_key"), _s("items")),
    Step("match", steps.match, "Match two sides", _s("case_key"), _s("items")),
    Step("resolve", steps.resolve, "Reference lookups", _s("items"), _s("items")),
    Step("compare", steps.compare, "Compare to baseline", _s("items"), _s("items")),
    Step("group", steps.group, "Group", _s("items"), _s("groups")),
    Step("reason", steps.reason, "Rules, then model", _s("items", "groups"), _s("findings")),
    Step("draft", steps.draft, "Draft", _s("groups", "findings"), _s("draft")),
    Step("validate", steps.validate, "Validate figures", _s("findings", "groups"),
         _s("findings", "validation_errors"), gate=True),
    Step("review", steps.review, "Human review", _s("findings", "draft"),
         _s("review_cycles"), gate=True),
    Step("record", steps.record, "Record", _s("groups", "findings", "decisions"),
         _s("outcome"), gate=True),
    Step("publish", steps.publish, "Publish (write-back)", _s("groups", "findings", "decisions"),
         _s("outcome", "published")),
]}

GATES = ("validate", "review", "record")
INITIAL = _s("case_id", "capability_id", "manifest_version", "manifest", "case_key", "caller")
ON_RESUME = _s("decisions", "publish_approval")


def catalogue() -> list[dict]:
    return [{"name": s.name, "label": s.label, "gate": s.gate,
             "needs": sorted(s.needs), "produces": sorted(s.produces)} for s in STEPS.values()]


def order_problems(order: list[str], pause_before: list[str]) -> list[str]:
    out = [f"unknown step `{n}`" for n in order if n not in STEPS]
    if out:
        return out
    if len(set(order)) != len(order):
        out.append("a step is listed twice")
    for gate in GATES:
        if gate not in order:
            out.append(f"`{gate}` is required")
    if all(g in order for g in GATES) and not (
        order.index("validate") < order.index("review") < order.index("record")
    ):
        out.append("gates must run in the order validate → review → record")
    tail = ["record", "publish"] if "publish" in order else ["record"]
    if "review" in order and order[-len(tail):] != tail:
        out.append("`record` must be the last step" if tail == ["record"]
                   else "`publish` must come right after `record`, last")
    if "publish" in order and "publish" not in pause_before:
        out.append("the run must pause before `publish` for a second approval")
    if "review" not in pause_before:
        out.append("the run must pause before `review`")
    out += [f"pause_before: unknown step `{n}`" for n in pause_before if n not in order]
    have = set(INITIAL)
    for name in order:
        if name == "record":
            have |= ON_RESUME
        missing = STEPS[name].needs - have
        if missing:
            out.append(f"`{name}` needs {', '.join(sorted(missing))}, produced by no earlier step")
        have |= STEPS[name].produces
    return out


def _traced(step: Step):
    async def run(state: CaseState) -> dict:
        with span(f"step.{step.name}", case_id=state["case_id"],
                  capability_id=state["capability_id"], gate=step.gate):
            return await step.fn(state)
    return run


def build_graph(order: list[str], pause_before: list[str], checkpointer):
    g = StateGraph(CaseState)
    for name in order:
        g.add_node(name, _traced(STEPS[name]))
    g.add_node("escalate", steps.escalate)
    g.set_entry_point(order[0])
    for current, following in zip(order, order[1:] + [None]):
        if following is None:
            g.add_edge(current, END)
        elif current in ("review", "record", "publish"):
            g.add_edge(current, following)
        else:
            g.add_conditional_edges(
                current,
                lambda st, nxt=following: "escalate" if st.get("outcome") == ESCALATED else nxt,
                {following: following, "escalate": "escalate"},
            )
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer, interrupt_before=list(pause_before))


@asynccontextmanager
async def checkpointer():
    async with AsyncPostgresSaver.from_conn_string(checkpoint_dsn()) as cp:
        yield cp


async def setup_checkpointer() -> None:
    """Run once at startup, outside any open transaction (its migrations
    include CREATE INDEX CONCURRENTLY)."""
    async with checkpointer() as cp:
        await cp.setup()
