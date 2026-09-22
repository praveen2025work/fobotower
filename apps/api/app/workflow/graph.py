"""Graph wiring.

The sequence is fixed: resolve -> gather -> group -> rank -> draft ->
validate -> review (interrupt) -> record. The model never chooses what
happens next. Escalation short-circuits out of resolve or gather.

thread_id = investigation_session_id, at rec/book/run grain, so the review
interrupt fires once per session and the controller approves per pattern
group rather than per break.
"""

from functools import partial

from langgraph.graph import END, StateGraph

from app.workflow.nodes.draft import draft
from app.workflow.nodes.escalate import escalate
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.rank import rank
from app.workflow.nodes.record import record
from app.workflow.nodes.resolve import resolve
from app.workflow.nodes.validate import validate
from app.workflow.state import InvestigationState

ESCALATED = "escalated"


def _route(state: InvestigationState) -> str:
    return "escalate" if state.get("outcome") == ESCALATED else "continue"


def build_graph(checkpointer, *, session=None):
    def bind(fn):
        return partial(fn, session=session) if session is not None else fn

    async def review(state: InvestigationState) -> dict:
        """Pure pass-through. The pause happens at interrupt_before."""
        return {"review_cycles": state.get("review_cycles", 0) + 1}

    g = StateGraph(InvestigationState)
    g.add_node("resolve", bind(resolve))
    g.add_node("gather", bind(gather))
    g.add_node("group", bind(group))
    g.add_node("rank", bind(rank))
    g.add_node("draft", bind(draft))
    g.add_node("validate", bind(validate))
    g.add_node("review", review)
    g.add_node("record", bind(record))
    g.add_node("escalate", escalate)

    g.set_entry_point("resolve")
    g.add_conditional_edges(
        "resolve", _route, {"continue": "gather", "escalate": "escalate"}
    )
    g.add_conditional_edges(
        "gather", _route, {"continue": "group", "escalate": "escalate"}
    )
    g.add_edge("group", "rank")
    g.add_edge("rank", "draft")
    g.add_edge("draft", "validate")
    g.add_edge("validate", "review")
    g.add_edge("review", "record")
    g.add_edge("record", END)
    g.add_edge("escalate", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["review"])


async def run_investigation(state, *, thread_id, session, checkpointer):
    app = build_graph(checkpointer, session=session)
    config = {"configurable": {"thread_id": thread_id}}
    await app.ainvoke(state, config)
    return (await app.aget_state(config)).values


async def resume_investigation(thread_id, decisions, *, session, checkpointer):
    app = build_graph(checkpointer, session=session)
    config = {"configurable": {"thread_id": thread_id}}
    await app.aupdate_state(config, {"decisions": decisions})
    await app.ainvoke(None, config)
    return (await app.aget_state(config)).values
