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

from agent_one_finance import steps
from agent_one_finance.db import checkpoint_dsn
from agent_one_finance.observability import span
from agent_one_finance.steps import ESCALATED, CaseState


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
    Step("enrich", steps.enrich, "Enrich items", _s("items"), _s("items")),
    Step("resolve", steps.resolve, "Reference lookups", _s("items"), _s("items")),
    Step("classify", steps.classify, "Cause checks", _s("items"), _s("items")),
    Step("compare", steps.compare, "Compare to baseline", _s("items"), _s("items")),
    Step("group", steps.group, "Group", _s("items"), _s("groups")),
    Step("reason", steps.reason, "Rules, then model", _s("items", "groups"), _s("findings")),
    Step("agent", steps.agent, "Skill session (the model, with the allowed tools)", _s("case_key"),
         _s("items", "groups", "findings")),
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
# Steps that write the decided outcome to a bank system, after a second person releases it.
RELEASE_TYPES = ("publish", "post")
# Step types allowed after `record`.
AFTER_RECORD = ("publish", "post", "report")
# Step types the run waits before for something other than a person (an event, child cases).
WAIT_TYPES = ("await",)
INITIAL = _s("case_id", "capability_id", "manifest_version", "manifest", "case_key", "caller")
ON_RESUME = _s("decisions", "publish_approval")


def catalogue() -> list[dict]:
    from agent_one_finance import stepkit
    return [{"name": s.name, "label": s.label, "gate": s.gate,
             "needs": sorted(s.needs), "produces": sorted(s.produces)} for s in STEPS.values()] + [
        {"name": t["name"], "label": t["label"], "gate": False, "configurable": True, "says": t["says"],
         "schema": t["schema"], "needs": [], "produces": []} for t in stepkit.catalogue()]


def _io(step_id: str, types: dict[str, str], configs: dict) -> tuple[frozenset[str], frozenset[str]]:
    """What a step needs and produces: a core step's declaration, or a
    configurable step's, which depends on its settings (e.g. which data set)."""
    from agent_one_finance import stepkit
    t = types.get(step_id, step_id)
    if t in STEPS:
        return STEPS[t].needs, STEPS[t].produces
    st, cfg = stepkit.TYPES[t], configs.get(step_id)
    return frozenset(st.needs(cfg)), frozenset(st.produces(cfg))


def order_problems(order: list[str], pause_before: list[str], types: dict[str, str] | None = None,
                   configs: dict | None = None) -> list[str]:
    from agent_one_finance import stepkit
    types = types or {}
    configs = configs or {}
    out = [f"unknown step `{n}`" for n in order
           if types.get(n, n) not in STEPS and types.get(n, n) not in stepkit.TYPES]
    out += [f"`{n}` is a {types[n]} step; give it its settings under step_settings"
            for n in order if types.get(n, n) in stepkit.TYPES and n not in configs]
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
    # After `record` only actions on the decided outcome may run: one release
    # step (publish, or post for journals) — always after a second person's
    # release — and reports.
    kind = lambda n: types.get(n, n)  # noqa: E731
    releases = [n for n in order if kind(n) in RELEASE_TYPES]
    if len(releases) > 1:
        out.append("one write-back step only (publish or post)")
    if "record" in order:
        after = order[order.index("record") + 1:]
        for n in releases:
            if order.index(n) < order.index("record"):
                out.append(f"`{n}` must come right after `record`, last" if n == "publish"
                           else f"`{n}` must come after `record`")
        bad = [n for n in after if kind(n) not in AFTER_RECORD]
        if bad:
            out.append(f"after `record` only write-back and report steps may run (not {', '.join(bad)})")
    for n in releases:
        if n not in pause_before:
            out.append(f"the run must pause before `{n}` for a second approval")
    if "review" not in pause_before:
        out.append("the run must pause before `review`")
    out += [f"pause_before: unknown step `{n}`" for n in pause_before if n not in order]
    have = set(INITIAL)
    for name in order:
        if name == "record":
            have |= ON_RESUME
        needs, produces = _io(name, types, configs)
        missing = needs - have
        if missing:
            words = [f"data set `{x[8:]}`" if x.startswith("dataset:") else x for x in sorted(missing)]
            out.append(f"`{name}` needs {', '.join(words)}, produced by no earlier step")
        have |= produces
    return out


def _traced(step_id: str, step_type: str):
    """A node: runs a core step or a configurable one, unless its `when` says
    to skip it this time (a skipped step is recorded on the case)."""
    from agent_one_finance import rules, stepkit
    from agent_one_finance.manifest import Manifest

    async def run(state: CaseState) -> dict:
        m = Manifest.model_validate(state["manifest"])
        st = m.step_settings.get(step_id)
        with span(f"step.{step_id}", case_id=state["case_id"], capability_id=state["capability_id"],
                  gate=step_type in GATES, step_type=step_type) as sp:
            if st and st.when:
                env = {"case": dict(state["case_key"]), "policy": m.policy_values(),
                       "count": len(state.get("items") or [])}
                try:
                    go = bool(rules.evaluate(st.when, env))
                except rules.ExpressionError:
                    go = True          # cannot tell: run it rather than skip a control
                if not go:
                    sp.set_attribute("aof.skipped", True)
                    return {"skipped": [*(state.get("skipped") or []), step_id]}
            if step_type in STEPS:
                return await STEPS[step_type].fn(state)
            return await stepkit.TYPES[step_type].run(state, m.step_config(step_id), step_id)
    return run


def build_graph(order: list[str], pause_before: list[str], checkpointer, types: dict[str, str] | None = None):
    types = types or {}
    g = StateGraph(CaseState)
    for name in order:
        g.add_node(name, _traced(name, types.get(name, name)))
    g.add_node("escalate", steps.escalate)
    g.set_entry_point(order[0])
    for current, following in zip(order, order[1:] + [None]):
        if following is None:
            g.add_edge(current, END)
        elif current in ("review", "record") or types.get(current, current) in AFTER_RECORD:
            g.add_edge(current, following)
        else:
            g.add_conditional_edges(
                current,
                lambda st, nxt=following: "escalate" if st.get("outcome") == ESCALATED else nxt,
                {following: following, "escalate": "escalate"},
            )
    g.add_edge("escalate", END)
    waits = [n for n in order if types.get(n, n) in WAIT_TYPES]
    return g.compile(checkpointer=checkpointer, interrupt_before=list(dict.fromkeys([*pause_before, *waits])))


@asynccontextmanager
async def checkpointer():
    async with AsyncPostgresSaver.from_conn_string(checkpoint_dsn()) as cp:
        yield cp


async def setup_checkpointer() -> None:
    """Run once at startup, outside any open transaction (its migrations
    include CREATE INDEX CONCURRENTLY)."""
    async with checkpointer() as cp:
        await cp.setup()
