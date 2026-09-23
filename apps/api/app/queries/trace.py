"""The investigation's execution trace, read from LangGraph checkpoints.

LangGraph saves a checkpoint after every step, so the run's history is real
recorded data rather than something reconstructed for display: which node
ran, in what order, how long it took, and what it added to the state.

Which node ran is read from each checkpoint's `next`: the checkpoint at step
k names the node that runs between step k and step k+1.
"""

from app.workflow.graph import build_graph

# The workflow in execution order, as wired in app/workflow/graph.py. Listed
# here so the trace can show steps that have not run yet.
WORKFLOW = [
    ("resolve", "Resolve books", "Pin each break's book to the business date"),
    ("gather", "Gather evidence", "Deltas, cause checks, lineage and priors"),
    ("group", "Group patterns", "Collapse breaks into pattern groups"),
    ("reason", "Apply playbook", "Settle by rule; route the rest to the reasoner"),
    ("rank", "Rank causes", "Order candidate causes per break"),
    ("draft", "Draft analysis", "Write the four-part narrative"),
    ("validate", "Validate", "Check every figure traces to a delta"),
    ("review", "Human sign-off", "Controller approves or rejects"),
    ("record", "Record outcome", "Write decisions; they become tomorrow's priors"),
]
NODE_INDEX = {name: i for i, (name, _l, _d) in enumerate(WORKFLOW)}


def _summary(node: str, v: dict) -> str:
    """What the node produced, in a line a controller can read."""
    if node == "resolve":
        return f"{len(v.get('book_resolutions') or {})} books resolved as of {v.get('as_of')}"
    if node == "gather":
        checks = sum(len(c) for c in (v.get("candidates") or {}).values())
        priors = sum(len(p) for p in (v.get("priors") or {}).values())
        return f"{len(v.get('deltas') or {})} deltas · {checks} cause checks · {priors} priors"
    if node == "group":
        return f"{len(v.get('pattern_groups') or [])} pattern groups from {len(v.get('breaks') or [])} breaks"
    if node == "reason":
        d = v.get("determinism") or {}
        if not d:
            return "no determination recorded"
        return (f"{d.get('deterministic', 0)} of {d.get('total', 0)} settled by playbook"
                f" · {d.get('escalated_to_reasoner', 0)} need judgement")
    if node == "rank":
        return "no model needed" if v.get("model_skipped") else "some breaks need a model"
    if node == "draft":
        return "analysis drafted" if v.get("draft") else "no draft"
    if node == "validate":
        errs = v.get("validation_errors") or []
        return "every figure grounded" if not errs else f"{len(errs)} validation notes"
    if node == "review":
        return "awaiting controller sign-off"
    if node == "record":
        return f"outcome: {v.get('outcome')}" if v.get("outcome") else "not yet recorded"
    return ""


def _added_keys(before: dict, after: dict) -> list[str]:
    return sorted(k for k in after if after.get(k) != before.get(k) and not k.startswith("_"))


async def execution_trace(checkpointer, session, thread_id: str) -> dict:
    graph = build_graph(checkpointer, session=session)
    config = {"configurable": {"thread_id": thread_id}}
    history = [snap async for snap in graph.aget_state_history(config)]
    history.reverse()  # oldest first

    if not history:
        return {"thread_id": thread_id, "status": "not_started", "steps": [
            {"node": n, "label": l, "description": d, "status": "pending"}
            for n, l, d in WORKFLOW
        ]}

    ran: dict[str, dict] = {}
    for i, snap in enumerate(history):
        if not snap.next:
            continue
        node = snap.next[0]
        if node not in NODE_INDEX or i + 1 >= len(history):
            continue
        after = history[i + 1]
        started, finished = snap.created_at, after.created_at
        ran[node] = {
            "started_at": started,
            "duration_ms": _ms_between(started, finished),
            "produced": _added_keys(snap.values or {}, after.values or {}),
            "summary": _summary(node, after.values or {}),
        }

    latest = history[-1]
    parked_at = latest.next[0] if latest.next else None
    escalated = (latest.values or {}).get("outcome") == "escalated"

    steps = []
    for name, label, desc in WORKFLOW:
        step = {"node": name, "label": label, "description": desc}
        if name in ran:
            step.update(status="done", **ran[name])
        elif name == parked_at:
            step.update(status="waiting", summary=_summary(name, latest.values or {}))
        else:
            step.update(status="skipped" if escalated else "pending")
        steps.append(step)

    status = ("escalated" if escalated
              else "awaiting_signoff" if parked_at == "review"
              else (latest.values or {}).get("outcome") or "running")
    return {
        "thread_id": thread_id,
        "status": status,
        "parked_at": parked_at,
        "checkpoints": len(history),
        "total_ms": sum(s.get("duration_ms") or 0 for s in steps),
        "steps": steps,
        "escalation_reason": (latest.values or {}).get("escalation_reason"),
    }


def _ms_between(a: str, b: str) -> int | None:
    from datetime import datetime

    try:
        return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None
