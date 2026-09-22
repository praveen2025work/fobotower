"""Test isolation.

Tests run against their own database. They truncate every table before each
test, and pointing that at the development database destroys whatever the
dev server was serving — the schedule, the seeded history, everything.

The environment variable is set before any application module is imported,
because app.db.base builds its engine at import time.
"""

import os

TEST_DATABASE_URL = os.getenv(
    "FOBO_TEST_DATABASE_URL",
    "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_test",
)
os.environ["FOBO_DATABASE_URL"] = TEST_DATABASE_URL

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import models_graph, models_ops, models_session  # noqa: E402,F401
from app.db.base import Base, engine, get_session  # noqa: E402

# Child tables first.
TABLES = [
    "source_call",
    "controller_decision",
    "pattern_group",
    "evidence_item",
    "analysis_version",
    "investigation_session",
    "break_embedding",
    "break_event",
    "edge",
    "node",
    "run",
    "reconciliation",
]


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
    """Create the test database and its schema once per session.

    create_all rather than alembic: migrations are exercised against the
    development database, and tests want a fast, exact mirror of the models.
    """
    await _create_database_if_missing()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


# LangGraph owns these and creates them lazily. They outlive a truncation of
# the application tables, and a stale checkpoint makes a route think an
# investigation already ran — so the session row it would have created never
# appears, and later inserts fail their foreign key.
CHECKPOINT_TABLES = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]


@pytest.fixture(autouse=True)
async def clean_tables(prepare_database):
    async with get_session() as s:
        await s.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
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
