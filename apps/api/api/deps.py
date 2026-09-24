"""Shared request-scoped helpers."""

import asyncio
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

# Whether the checkpoint tables/indexes have been created in this process.
_checkpointer_ready = False
_checkpointer_setup_lock = asyncio.Lock()


async def setup_checkpointer() -> None:
    """Create the checkpoint tables and indexes once per process.

    cp.setup() runs `CREATE INDEX CONCURRENTLY`, which cannot run inside a
    transaction and must wait for every transaction already open in the
    database to finish — including, if this runs lazily inside a request,
    that request's own SQLAlchemy session, which is left idle-in-transaction
    because nothing has committed it yet. The request then can't finish
    (it's waiting on setup() to return) and setup() can't finish (it's
    waiting on the request's transaction to end): a permanent deadlock, and
    on a brand-new database — one where these indexes don't already exist —
    the very first request to open an investigation hits it every time.
    Running this once at process startup, before any request can hold a
    transaction, avoids that. Guarded by a flag plus a lock so two
    concurrent first callers (e.g. FastAPI's lifespan racing a request that
    arrived before it finished) don't both run it.
    """
    global _checkpointer_ready
    if _checkpointer_ready:
        return
    async with _checkpointer_setup_lock:
        if _checkpointer_ready:
            return
        async with AsyncPostgresSaver.from_conn_string(CHECKPOINT_DSN) as cp:
            await cp.setup()
        _checkpointer_ready = True


@asynccontextmanager
async def checkpointer():
    await setup_checkpointer()
    async with AsyncPostgresSaver.from_conn_string(CHECKPOINT_DSN) as cp:
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
