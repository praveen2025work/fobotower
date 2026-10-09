"""Test isolation.

Tests run against their own database. They truncate every table before each
test, and pointing that at the development database destroys whatever the
dev server was serving — the schedule, the seeded history, everything.

The environment variable is set before any application module is imported,
because the database engine is built at import time.
"""

import os

TEST_DATABASE_URL = (os.getenv("AOF_TEST_DATABASE_URL") or os.getenv("FOBO_TEST_DATABASE_URL")
                     or "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_test")
os.environ["FOBO_DATABASE_URL"] = TEST_DATABASE_URL
# Agent One Finance case runs finish before the call returns, unless a test asks otherwise.
os.environ.setdefault("AOF_RUN_MODE", "inline")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from agent_one_finance.db import engine, get_session  # noqa: E402
from agent_one_finance.workflow import setup_checkpointer  # noqa: E402


def _admin_dsn() -> str:
    """The same server, but the default database, so CREATE DATABASE works."""
    raw = TEST_DATABASE_URL.replace("+asyncpg", "")
    return raw.rsplit("/", 1)[0] + "/postgres"


async def _create_database_if_missing() -> None:
    conn = await asyncpg.connect(_admin_dsn())
    try:
        name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    """Create the test database once per session, with LangGraph's checkpoint
    tables (the Agent One Finance tables are created by tests/agent_one_finance/conftest.py)."""
    await _create_database_if_missing()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await setup_checkpointer()
    yield
    await engine.dispose()


# LangGraph owns these and creates them lazily. A stale checkpoint makes a
# case think it already ran, so they are emptied before each test.
CHECKPOINT_TABLES = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]


@pytest.fixture(autouse=True)
async def clean_tables(prepare_database):
    async with get_session() as s:
        for name in CHECKPOINT_TABLES:
            await s.execute(
                text(
                    "DO $$ BEGIN "
                    f"IF to_regclass('public.{name}') IS NOT NULL THEN "
                    f"TRUNCATE {name} CASCADE; END IF; END $$;"
                )
            )
        await s.commit()
    yield
