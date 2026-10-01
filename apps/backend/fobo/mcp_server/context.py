"""What a bearer token stands for: one agent session's scope.

Frozen so a tool cannot widen its own scope mid-call. The caller and business
date are the ones the investigation was started with; the agent never gets to
pick either.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from fobo.contracts.models import Caller
from fobo.reasoning.agent_sessions import find_active_by_token


@dataclass(frozen=True)
class AgentContext:
    investigation_session_id: str
    caller: Caller
    business_date: date
    breaks: dict[str, dict]


async def context_for_token(session: AsyncSession, token: str) -> AgentContext | None:
    """The context for a live session's token, or None for any other token."""
    row = await find_active_by_token(session, token)
    if row is None:
        return None
    return AgentContext(
        investigation_session_id=row.investigation_session_id,
        caller=Caller.model_validate(row.caller),
        business_date=row.business_date,
        breaks=dict(row.breaks),
    )
