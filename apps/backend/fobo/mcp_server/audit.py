"""Every tool call is one source_call row, success or failure.

That row is what the console's MCP data panel shows and what the audit record
relies on: a retrieval with no row is invisible to both. The row is committed
here, so a tool error still leaves its trace before it is re-raised.
"""

import time
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from fobo.grounding.recorder import GroundingRecorder
from fobo.mcp_server.context import AgentContext
from fobo.mcp_server.tools import ToolInputError

APPLICATION = "agent"


def _shape(result: dict, rows_key: str | None) -> tuple[int, str, list[dict]]:
    """Row count and rows for the audit row.

    The caller names which key holds the result's rows; without one the result
    is a single record. Guessing the first list would count a break's checks
    as the break's rows.
    """
    if rows_key is None:
        return 1, "1 record", [result]
    items = result[rows_key]
    rows = [i if isinstance(i, dict) else {"value": i} for i in items]
    return len(items), f"{len(items)} rows", rows


async def audited(
    session: AsyncSession,
    ctx: AgentContext,
    tool_name: str,
    params: dict,
    fn: Callable[[], Awaitable[dict]],
    rows_key: str | None = None,
) -> dict:
    recorder = GroundingRecorder(session, ctx.investigation_session_id)
    started = time.perf_counter()
    try:
        result = await fn()
    except Exception as exc:
        if not isinstance(exc, ToolInputError):
            # A database error leaves the transaction unusable for the audit row.
            await session.rollback()
        await recorder.record(
            application=APPLICATION, tool=tool_name, params=params, row_count=0,
            summary="error", latency_ms=_ms(started), error=str(exc), rows=None,
        )
        await session.commit()
        raise
    row_count, summary, rows = _shape(result, rows_key)
    await recorder.record(
        application=APPLICATION, tool=tool_name, params=params, row_count=row_count,
        summary=summary, latency_ms=_ms(started), rows=rows,
    )
    await session.commit()
    return result


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
