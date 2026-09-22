"""Controller decisions: approve or reject a pattern group, or one break.

Every request carries an Idempotency-Key. A repeat returns 409 rather than
recording a second decision: a duplicated P&L adjustment is the worst
available outcome, and a retry on a flaky connection is the likeliest way
to cause one.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.auth import current_caller
from api.deps import checkpointer
from api.routes.recs import session_id_for
from app.db.base import get_session
from app.db.models_graph import BreakEvent
from app.db.models_session import ControllerDecision, PatternGroupRow
from app.workflow.graph import build_graph
from app.workflow.session import ensure_investigation_session

router = APIRouter(prefix="/api/recs", tags=["decisions"])

ACTIONS = ("approve", "reject")


class DecisionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    reason: str | None = None
    group_id: str | None = None
    break_id: str | None = None


async def _already_recorded(s, key: str) -> ControllerDecision | None:
    return await s.scalar(
        select(ControllerDecision).where(ControllerDecision.idempotency_key == key)
    )


@router.post("/{rec_id}/decisions", status_code=201)
async def record_decision(
    rec_id: str,
    body: DecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict:
    if body.action == "reject" and not (body.reason or "").strip():
        # An empty rejection gives the retry cycle nothing to correct.
        raise HTTPException(status_code=422, detail="a rejection requires a reason")

    sid = session_id_for(rec_id)
    caller = current_caller()

    async with get_session() as s:
        if await _already_recorded(s, idempotency_key):
            raise HTTPException(
                status_code=409, detail="this decision was already recorded"
            )

        async with checkpointer() as cp:
            snapshot = await build_graph(cp, session=s).aget_state(
                {"configurable": {"thread_id": sid}}
            )
        if not snapshot.values:
            raise HTTPException(status_code=404, detail=f"no open case for {rec_id}")

        # The case exists in the checkpoint; make sure its session row does
        # too, so the decision's foreign key resolves.
        await ensure_investigation_session(s, snapshot.values)

        groups = {g.group_id: g for g in snapshot.values.get("pattern_groups", [])}
        if body.group_id and body.group_id not in groups:
            raise HTTPException(status_code=404, detail="no such pattern group")

        break_ids = (
            [body.break_id]
            if body.break_id
            else list(groups[body.group_id].break_ids)
            if body.group_id
            else []
        )
        if not break_ids:
            raise HTTPException(
                status_code=422, detail="supply a group_id or a break_id"
            )

        group = groups.get(body.group_id) if body.group_id else None
        if group is not None and await s.get(PatternGroupRow, group.group_id) is None:
            s.add(
                PatternGroupRow(
                    group_id=group.group_id,
                    investigation_session_id=sid,
                    pattern_code=group.pattern_code,
                    label=group.label,
                    mode=group.mode,
                    break_ids=group.break_ids,
                    historical_approval_rate=group.historical_approval_rate,
                )
            )
            await s.flush()

        decision_id = str(uuid.uuid4())
        s.add(
            ControllerDecision(
                decision_id=decision_id,
                investigation_session_id=sid,
                group_id=body.group_id,
                controller_user_id=caller.staff_id,
                action=body.action,
                reason=body.reason,
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
                if group is not None:
                    row.pattern_code = group.pattern_code
        await s.commit()

    return {
        "decision_id": decision_id,
        "action": body.action,
        "break_ids": break_ids,
        "idempotency_key": idempotency_key,
    }
