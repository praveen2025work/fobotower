"""Shared request-scoped helpers."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import func, select, text

from app.db.base import DATABASE_URL
from app.db.models_graph import Node
from app.playbook.loader import load_playbook, loaded_version
from fixtures.history import history_is_loaded, load_history
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
    """Transaction-scoped Postgres advisory lock.

    pg_advisory_xact_lock, not pg_advisory_lock: a session-scoped lock is held
    by a connection, and a commit inside the seed can return that connection
    to the pool — the matching unlock then runs on a different connection,
    silently fails, and the lock leaks until the backend dies. Every later
    request blocks forever on it.

    A transaction lock is released by the commit or rollback that ends this
    block, so it cannot outlive the work it guards. The seed therefore runs
    commit-free and is committed once, here.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": SEED_LOCK_KEY}
    )
    try:
        yield
        await session.commit()
    except Exception:
        await session.rollback()
        raise


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
            await load_all(session, commit=False)
        if not await history_is_loaded(session):
            await load_history(session, commit=False)
        if await loaded_version(session) is None:
            await load_playbook(session, commit=False)
