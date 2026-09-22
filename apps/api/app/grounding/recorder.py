"""Records every retrieval as a source_call row.

This is the Grounding panel's data, and the audit record's. A retrieval that
happens without a row here is invisible to both.
"""

import uuid

from sqlalchemy import select

from app.db.models_ops import SourceCall


class GroundingRecorder:
    def __init__(self, session, investigation_session_id: str):
        self._s = session
        self._sid = investigation_session_id
        self._seq = 0

    async def record(
        self,
        *,
        application: str,
        tool: str,
        params: dict,
        row_count: int | None,
        summary: str,
        entitlement: str = "allowed",
        latency_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        # Sequence in the id, so call order survives identical timestamps.
        self._s.add(
            SourceCall(
                call_id=f"{self._sid}:{self._seq:04d}:{uuid.uuid4().hex[:8]}",
                investigation_session_id=self._sid,
                application_name=application,
                tool_name=tool,
                validated_parameters=params,
                row_count=row_count,
                result_summary=summary,
                entitlement_result=entitlement,
                latency_ms=latency_ms,
                error_detail=error,
            )
        )
        self._seq += 1


async def calls_for(session, investigation_session_id: str) -> list[dict]:
    rows = (
        await session.scalars(
            select(SourceCall)
            .where(SourceCall.investigation_session_id == investigation_session_id)
            .order_by(SourceCall.call_id)
        )
    ).all()
    return [
        {
            "call_id": r.call_id,
            "application": r.application_name,
            "tool": r.tool_name,
            "params": r.validated_parameters,
            "row_count": r.row_count,
            "summary": r.result_summary,
            "entitlement_result": r.entitlement_result,
            "latency_ms": r.latency_ms,
            "error": r.error_detail,
        }
        for r in rows
    ]
