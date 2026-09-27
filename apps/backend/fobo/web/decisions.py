"""Controller decisions: approve or reject a set of breaks.

Every request carries an Idempotency-Key. A repeat returns 409 rather than
recording a second decision: a duplicated P&L adjustment is the worst
available outcome, and a retry on a flaky connection is the likeliest way
to cause one.

Not a route module: the console reaches this through
`POST /api/recs/{id}/decisions` in fobo/web/routes/console.py, which is the only
caller. That handler always supplies `break_ids` (the console confirms a
selection of adjustment rows, never a bare pattern group or a single break),
so this module only supports that path — the classic action/group_id/break_id
body, and the group_id-keyed decision it enabled, are dropped (spec §5).
"""

import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from fobo.web.auth import current_caller
from fobo.web.investigations import session_id_for
from fobo.web.dependencies import checkpointer
from fobo.db.models_graph import BreakEvent
from fobo.db.models_session import ControllerDecision
from fobo.investigation.graph import graph_for_session
from fobo.investigation.session import ensure_investigation_session


class DecisionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reason: str | None = None
    # The breaks this decision covers — the console confirms a selection.
    break_ids: list[str] = Field(min_length=1)


async def _already_recorded(s, key: str) -> ControllerDecision | None:
    return await s.scalar(
        select(ControllerDecision).where(ControllerDecision.idempotency_key == key)
    )


async def apply_decision(s, rec_id: str, body: DecisionRequest,
                         idempotency_key: str) -> dict:
    """Record one controller decision and set its breaks' outcomes."""
    if body.action == "reject" and not (body.reason or "").strip():
        # An empty rejection gives the retry cycle nothing to correct.
        raise HTTPException(status_code=422, detail="a rejection requires a reason")

    sid = session_id_for(rec_id)
    caller = current_caller()

    if await _already_recorded(s, idempotency_key):
        raise HTTPException(
            status_code=409, detail="this decision was already recorded"
        )

    async with checkpointer() as cp:
        graph, _ = await graph_for_session(cp, s, sid)
        snapshot = await graph.aget_state({"configurable": {"thread_id": sid}})
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"no open case for {rec_id}")

    # The case exists in the checkpoint; make sure its session row does
    # too, so the decision's foreign key resolves.
    await ensure_investigation_session(s, snapshot.values)

    drafted = {
        b for g in snapshot.values.get("pattern_groups", []) for b in g.break_ids
    }
    break_ids = list(body.break_ids)
    unknown = [b for b in break_ids if b not in drafted]
    if unknown:
        raise HTTPException(
            status_code=404, detail=f"not drafted in this case: {', '.join(unknown)}"
        )

    decision_id = str(uuid.uuid4())
    s.add(
        ControllerDecision(
            decision_id=decision_id,
            investigation_session_id=sid,
            controller_user_id=caller.staff_id,
            action=body.action,
            reason=body.reason,
            break_ids=break_ids,
            idempotency_key=idempotency_key,
        )
    )

    outcome = "approved" if body.action == "approve" else "rejected"
    for bid in break_ids:
        row = await s.scalar(
            select(BreakEvent).where(BreakEvent.break_id == bid)
        )
        if row is not None:
            row.outcome = outcome
    await s.commit()

    return {
        "decision_id": decision_id,
        "action": body.action,
        "break_ids": break_ids,
        "idempotency_key": idempotency_key,
    }
