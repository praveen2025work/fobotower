"""Transactional write of the outcome.

Today's decision becomes tomorrow's prior: each break is stamped with its
pattern code and outcome so similar_breaks can find it on a later run.
"""

import uuid

from sqlalchemy import select

from app.db.models_graph import BreakEvent
from app.db.models_session import AnalysisVersion, InvestigationSession, PatternGroupRow
from app.workflow.state import InvestigationState


async def record(state: InvestigationState, *, session) -> dict:
    sid = state["investigation_session_id"]
    approved = {
        d["group_id"] for d in state.get("decisions", []) if d["action"] == "approve"
    }

    existing = await session.get(InvestigationSession, sid)
    if existing is None:
        session.add(
            InvestigationSession(
                investigation_session_id=sid,
                reconciliation_id=state["reconciliation_id"],
                master_book=state["master_book"],
                business_date=state["business_date"],
                run_id=state["run_id"],
                status="recorded",
            )
        )
    else:
        existing.status = "recorded"
    await session.flush()

    for g in state["pattern_groups"]:
        if await session.get(PatternGroupRow, g.group_id) is None:
            session.add(
                PatternGroupRow(
                    group_id=g.group_id,
                    investigation_session_id=sid,
                    pattern_code=g.pattern_code,
                    label=g.label,
                    mode=g.mode,
                    break_ids=g.break_ids,
                    historical_approval_rate=g.historical_approval_rate,
                )
            )
        outcome = "approved" if g.group_id in approved else "rejected"
        for bid in g.break_ids:
            brk = await session.scalar(
                select(BreakEvent).where(BreakEvent.break_id == bid)
            )
            if brk is not None:
                brk.pattern_code = g.pattern_code
                brk.outcome = outcome
                brk.narrative = g.label

    d = state["draft"]
    session.add(
        AnalysisVersion(
            analysis_version_id=str(uuid.uuid4()),
            investigation_session_id=sid,
            supersedes=None,
            summary=d.model_dump(),
            confidence_tier="high",
            prompt_version="phase1-template-v1",
            skill_version="phase1",
            model_identifier="none",
        )
    )
    await session.commit()
    return {"outcome": "recorded"}
