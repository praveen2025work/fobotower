"""Records every retrieval as a source_call row.

This is the Grounding panel's data, and the audit record's. A retrieval that
happens without a row here is invisible to both.
"""

import time
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
        rows: list[dict] | None = None,
    ) -> str:
        # Clock then sequence in the id, so ids sort in call order: across
        # recorders (gather, validate and chat each hold their own) by the
        # clock, and within one recorder by the sequence even when two calls
        # land on the same clock tick.
        call_id = f"{self._sid}:{time.time_ns():019d}{self._seq:03d}:{uuid.uuid4().hex[:6]}"
        self._s.add(
            SourceCall(
                call_id=call_id,
                investigation_session_id=self._sid,
                application_name=application,
                tool_name=tool,
                validated_parameters=params,
                row_count=row_count,
                result_summary=summary,
                entitlement_result=entitlement,
                latency_ms=latency_ms,
                error_detail=error,
                result_rows=rows,
            )
        )
        self._seq += 1
        return call_id


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
            "rows": r.result_rows,
            "called_ts": r.called_ts.isoformat() if r.called_ts else None,
        }
        for r in rows
    ]
