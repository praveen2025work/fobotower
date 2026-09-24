"""Graph wiring — built from the workflow config.

The steps, their order, and where the run pauses for a person come from
config/workflow/fobo-investigation.yaml, validated against the step registry
before this runs. The model never chooses what happens next: the order is
fixed by the config, and the config cannot drop the safety steps.

A step that can escalate (resolve, gather) routes to `escalate` when it
does, and to the next configured step when it does not.

thread_id = investigation_session_id, at rec/book/run grain, so the review
pause fires once per session and the controller approves per pattern group.
"""

from functools import partial

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.db.models_session import InvestigationSession
from app.workflow.config import WorkflowConfig, use_workflow, workflow
from app.workflow.nodes.escalate import escalate
from app.workflow.registry import STEPS
from app.workflow.session import ensure_investigation_session
from app.workflow.state import InvestigationState

ESCALATED = "escalated"


def _router(next_step: str):
    def route(state: InvestigationState) -> str:
        return "escalate" if state.get("outcome") == ESCALATED else next_step
    return route


def build_graph(checkpointer, *, session=None, config: WorkflowConfig | None = None):
    cfg = config or workflow()

    def bind(step):
        fn = step.fn
        if step.uses_session and session is not None:
            return partial(fn, session=session)
        return fn

    g = StateGraph(InvestigationState)
    for name in cfg.steps:
        g.add_node(name, bind(STEPS[name]))
    g.add_node("escalate", escalate)

    g.set_entry_point(cfg.steps[0])
    for current, following in zip(cfg.steps, cfg.steps[1:] + [None]):
        target = following or END
        if STEPS[current].can_escalate and following:
            g.add_conditional_edges(
                current, _router(following),
                {following: following, "escalate": "escalate"},
            )
        else:
            g.add_edge(current, target)
    g.add_edge("escalate", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=list(cfg.pause_before))


async def pinned_for_session(session, thread_id: str):
    """The workflow a run started with, from its investigation_session row.

    No row: the run has not started, so it is shown with the workflow that
    would run now. A row without a version predates versioning: version 1.
    A column select, not session.get, so a row updated by a Core upsert is
    never read stale from the identity map.
    """
    from app.workflow import versions

    row = (await session.execute(
        select(InvestigationSession.investigation_session_id,
               InvestigationSession.workflow_version)
        .where(InvestigationSession.investigation_session_id == thread_id)
    )).first()
    if row is None:
        return await versions.active(session)
    return await versions.pinned(session, row.workflow_version or 1)


async def graph_for_session(checkpointer, session, thread_id: str):
    """The run's own graph, built from the version it was pinned to."""
    pinned = await pinned_for_session(session, thread_id)
    return build_graph(checkpointer, session=session, config=pinned.config), pinned


async def run_investigation(state, *, thread_id, session, checkpointer):
    from app.workflow import versions

    # The run is pinned to the version active now, for its whole life.
    pinned = await versions.active(session)
    state = {**state, "workflow_version": pinned.number}
    # source_call carries an FK to the session, and gather records as it
    # retrieves, so the row has to exist before the graph starts.
    await ensure_investigation_session(session, state)
    app = build_graph(checkpointer, session=session, config=pinned.config)
    config = {"configurable": {"thread_id": thread_id}}
    with use_workflow(pinned.config):
        await app.ainvoke(state, config)
    return (await app.aget_state(config)).values


async def resume_investigation(thread_id, decisions, *, session, checkpointer):
    app, pinned = await graph_for_session(checkpointer, session, thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    with use_workflow(pinned.config):
        await app.aupdate_state(config, {"decisions": decisions})
        await app.ainvoke(None, config)
    return (await app.aget_state(config)).values
