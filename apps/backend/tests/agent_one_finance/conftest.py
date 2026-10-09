"""Agent One Finance tests: self-contained, so this folder runs as it is in any repo that takes
AOF (aos-backend has its own tests/conftest.py).

They run against their own database, AOF_TEST_DATABASE_URL (default
postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_test), created if missing, with pgvector.
Every table is emptied before each test, so the tests refuse to run against a database whose
name does not end in "_test". These fixtures create the aof_* tables, empty them before each
test, and seed the capabilities from config/agent-one-finance."""

import os

TEST_DATABASE_URL = (os.getenv("AOF_TEST_DATABASE_URL") or os.getenv("FOBO_TEST_DATABASE_URL")
                     or "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_test")
# Set before AOF is imported: the database engine is built at import time.
os.environ["AOF_DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("AOF_RUN_MODE", "inline")  # case runs finish before the call returns

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text

from agent_one_finance import capabilities, knowledge, llm
from agent_one_finance import groups as team_groups
from agent_one_finance.db import AofBase, engine, get_session
from agent_one_finance.models import AOF_TABLES
from agent_one_finance.workflow import setup_checkpointer

if not (engine.url.database or "").endswith("_test"):
    pytest.exit(f"refusing to run the AOF tests against database {engine.url.database!r}: its tables are emptied. "
                "Point AOF_TEST_DATABASE_URL at a database whose name ends in _test.", returncode=2)

# LangGraph owns these and creates them lazily. A stale checkpoint makes a case think it
# already ran, so they are emptied before each test.
CHECKPOINT_TABLES = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]


@pytest.fixture(scope="session", autouse=True)
async def aof_database():
    """The test database, created if missing, with pgvector and LangGraph's checkpoint tables."""
    admin = TEST_DATABASE_URL.replace("+asyncpg", "").rsplit("/", 1)[0] + "/postgres"
    conn = await asyncpg.connect(admin)
    try:
        name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()
    async with engine.begin() as c:
        await c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await setup_checkpointer()
    yield
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def aof_schema(aof_database):
    # Rebuilt every session: create_all never alters an existing table, so a
    # schema change would otherwise leave an old test database silently stale.
    async with engine.begin() as conn:
        await conn.run_sync(AofBase.metadata.drop_all)
        await conn.run_sync(AofBase.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def aof_clean(aof_schema):
    async with get_session() as s:
        for name in CHECKPOINT_TABLES:
            await s.execute(text(f"DO $$ BEGIN IF to_regclass('public.{name}') IS NOT NULL THEN "
                                 f"TRUNCATE {name} CASCADE; END IF; END $$;"))
        await s.execute(text(f"TRUNCATE {', '.join(AOF_TABLES)} CASCADE"))
        await s.commit()
    await capabilities.seed()
    await team_groups.seed()
    await knowledge.seed_reference()
    llm._adapter = None  # each test picks its own LLM adapter
    yield
    llm._adapter = None


@pytest.fixture
async def api():
    from agent_one_finance.web.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        def as_user(user):
            return {"X-AOF-User": user}
        c.as_user = as_user
        yield c


_exporter = InMemorySpanExporter()


@pytest.fixture
def spans():
    """Finished spans of this test. OpenTelemetry allows one global provider
    per process, so it is installed once and cleared per test."""
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(_exporter))
        trace.set_tracer_provider(provider)
    _exporter.clear()
    return _exporter


VARIANCE = "fin.variance-commentary"
RECON = "recon.investigation"
CASH = "cash-bank-ledger"          # rec groups of RECON
FOBO = "cats-motif"
