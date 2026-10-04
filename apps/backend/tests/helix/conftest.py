"""Helix tests share the session's test database (tests/conftest.py points
FOBO_DATABASE_URL at it, and Helix falls back to that URL). These fixtures
create the helix_* tables, empty them before each test, and seed the
capabilities from config/helix."""

import pytest
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text

from helix import capabilities, llm
from helix import groups as team_groups
from helix.db import HelixBase, engine, get_session
from helix.models import HELIX_TABLES


@pytest.fixture(scope="session", autouse=True)
async def helix_schema(prepare_database):
    # Rebuilt every session: create_all never alters an existing table, so a
    # schema change would otherwise leave an old test database silently stale.
    async with engine.begin() as conn:
        await conn.run_sync(HelixBase.metadata.drop_all)
        await conn.run_sync(HelixBase.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def helix_clean(helix_schema, clean_tables):
    async with get_session() as s:
        await s.execute(text(f"TRUNCATE {', '.join(HELIX_TABLES)} CASCADE"))
        await s.commit()
    await capabilities.seed()
    await team_groups.seed()
    llm._adapter = None  # each test picks its own LLM adapter
    yield
    llm._adapter = None


@pytest.fixture
async def api():
    from helix.web.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        def as_user(user):
            return {"X-Helix-User": user}
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
