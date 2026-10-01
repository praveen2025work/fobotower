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


def _main_list(result: dict) -> list | None:
    return next((v for v in result.values() if isinstance(v, list)), None)


def _shape(result: dict) -> tuple[int, str, list[dict]]:
    items = _main_list(result)
    if items is None:
        return 1, "1 record", [result]
    rows = items if all(isinstance(i, dict) for i in items) else [result]
    return len(items), f"{len(items)} rows", rows


async def audited(
    session: AsyncSession,
    ctx: AgentContext,
    tool_name: str,
    params: dict,
    fn: Callable[[], Awaitable[dict]],
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
    row_count, summary, rows = _shape(result)
    await recorder.record(
        application=APPLICATION, tool=tool_name, params=params, row_count=row_count,
        summary=summary, latency_ms=_ms(started), rows=rows,
    )
    await session.commit()
    return result


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
