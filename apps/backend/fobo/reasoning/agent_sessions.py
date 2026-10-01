"""Repository for agent_session rows.

The Reason step runs one agent-harness session per L4 rec run. The row is
what makes that restart-safe (look up by investigation before starting) and
what lets the MCP server authenticate the session's bearer token: only the
sha256 of the token is stored, and a token is honoured only while the
session is starting or running.

Helpers flush nothing and commit nothing; the caller owns the transaction.
"""

import hashlib
import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fobo.db.models_session import AgentSession

ACTIVE_STATUSES = ("starting", "running")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """A fresh bearer token and its hash — store the hash, hand out the token."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


async def get_for_investigation(
    session: AsyncSession, investigation_session_id: str
) -> AgentSession | None:
    result = await session.execute(
        select(AgentSession).where(
            AgentSession.investigation_session_id == investigation_session_id
        )
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    investigation_session_id: str,
    token_hash: str,
    caller: dict,
    business_date: date,
    breaks: dict,
    request: dict,
) -> AgentSession:
    row = AgentSession(
        agent_session_id=f"{investigation_session_id}:agent",
        investigation_session_id=investigation_session_id,
        status="starting",
        token_hash=token_hash,
        caller=caller,
        business_date=business_date,
        breaks=breaks,
        request=request,
    )
    session.add(row)
    return row


async def mark_running(
    session: AsyncSession, row: AgentSession, harness_session_id: str
) -> None:
    row.status = "running"
    row.harness_session_id = harness_session_id


async def mark_completed(
    session: AsyncSession, row: AgentSession, response: dict
) -> None:
    row.status = "completed"
    row.response = response
    row.finished_ts = datetime.now(timezone.utc)


async def mark_failed(
    session: AsyncSession,
    row: AgentSession,
    error: str,
    response: dict | None = None,
) -> None:
    row.status = "failed"
    row.error = error
    row.response = response
    row.finished_ts = datetime.now(timezone.utc)


async def find_active_by_token(
    session: AsyncSession, token: str
) -> AgentSession | None:
    """The row this token belongs to, only while its session is live."""
    result = await session.execute(
        select(AgentSession).where(
            AgentSession.token_hash == hash_token(token),
            AgentSession.status.in_(ACTIVE_STATUSES),
        )
    )
    return result.scalar_one_or_none()
