"""Shared request-scoped helpers."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import func, select

from app.db.base import DATABASE_URL
from app.db.models_graph import Node
from fixtures.loader import load_all

# The checkpointer uses psycopg, not asyncpg.
CHECKPOINT_DSN = DATABASE_URL.replace("+asyncpg", "")


@asynccontextmanager
async def checkpointer():
    async with AsyncPostgresSaver.from_conn_string(CHECKPOINT_DSN) as cp:
        await cp.setup()
        yield cp


async def ensure_fixtures(session) -> None:
    """Seed the graph only when it is empty.

    Reloading on every investigate would wipe the outcomes `record` wrote,
    and those outcomes are what later runs read back as priors.
    """
    count = await session.scalar(select(func.count()).select_from(Node))
    if not count:
        await load_all(session)
