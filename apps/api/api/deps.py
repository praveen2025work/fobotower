"""Shared request-scoped helpers."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import func, select, text

from app.db.base import DATABASE_URL
from app.db.models_graph import Node
from fixtures.loader import load_all

# The checkpointer uses psycopg, not asyncpg.
CHECKPOINT_DSN = DATABASE_URL.replace("+asyncpg", "")

# Arbitrary but stable. Any process seeding this database uses the same key.
SEED_LOCK_KEY = 872155


@asynccontextmanager
async def checkpointer():
    async with AsyncPostgresSaver.from_conn_string(CHECKPOINT_DSN) as cp:
        await cp.setup()
        yield cp


@asynccontextmanager
async def _seed_lock(session):
    """Session-scoped Postgres advisory lock.

    Session-scoped rather than transaction-scoped because load_all commits
    internally, which would release a transaction lock half way through.
    """
    await session.execute(
        text("SELECT pg_advisory_lock(:key)"), {"key": SEED_LOCK_KEY}
    )
    try:
        yield
    finally:
        await session.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": SEED_LOCK_KEY}
        )
        await session.commit()


async def ensure_fixtures(session) -> None:
    """Seed the graph only when it is empty.

    Serialised, because the console issues two investigates at once in dev
    (React StrictMode double-fires effects). A bare check-then-act lets both
    requests see an empty graph and both seed: one then clears node rows the
    other is still inserting edges against, which surfaces as a foreign key
    violation and a 500. Holding the lock means the second request finds the
    graph already seeded and does nothing.

    Reloading on a non-empty graph would also wipe the outcomes `record`
    wrote, and those outcomes are what later runs read back as priors.
    """
    async with _seed_lock(session):
        count = await session.scalar(select(func.count()).select_from(Node))
        if not count:
            await load_all(session)
