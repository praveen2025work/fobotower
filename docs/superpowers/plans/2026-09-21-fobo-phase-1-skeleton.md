# FOBO Investigation Console — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the running skeleton — a LangGraph investigation that resolves books against a bitemporal graph, gathers evidence, groups breaks into patterns, drafts an analysis, pauses at a human interrupt, and resumes after a process restart — with a console that renders the Control Tower shell, run schedule and pipeline rail against it.

**Architecture:** Two orchestration lanes over one `investigation_session_id`. Phase 1 builds Lane 1 only (LangGraph, no model in the control flow) plus the console shell. Lane 2 (the Claude Agent SDK chat drawer) arrives in Phase 3. Every source adapter reads fixtures; four adapter classes are swapped at migration.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic · LangGraph · Postgres 16 + pgvector · pytest-asyncio · Next.js 16 · React 19 (JSX) · Tailwind v4 · Zustand · Vitest + React Testing Library

**Spec:** `docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md`

**Design source:** `docs/design/mock-tokens.css` — 114 design tokens extracted verbatim from `FoboControlTower (1).html`. Treat as read-only source material.

## Global Constraints

- **Python 3.12**, **Node 20+**. Pin LangGraph exactly; it is pre-1.0.
- **Ports are fixed and must not change**: console `3100`, API `8100`, Postgres `5433`. These are offset from AgentOne's defaults so both stacks run simultaneously.
- **Frontend is JavaScript/JSX only.** No `.ts` or `.tsx` under `apps/console/src`. Generated `.d.ts` files in `packages/contracts/dist` are the sole exception.
- **Every graph repository method takes `as_of` and `caller`.** Neither is optional. Neither has a default.
- **The entitlement predicate is injected into the query**, never applied after the fact.
- **No model call decides control flow.** Phase 1 contains no LLM calls at all; `draft` uses a deterministic template. The model arrives in Phase 3.
- **Reference graph rows are never updated in place.** A change closes the old edge (`valid_to = effective_date - 1`) and inserts a new one.
- **Commit after every task.** Conventional commits (`feat:`, `test:`, `chore:`).
- **Tests are written before implementation** and must be observed failing first.

---

## File Structure

```
apps/api/
  app/contracts/models.py        Pydantic source of truth for all events + entities
  app/db/base.py                 async engine, session factory
  app/db/models_session.py       investigation_session, interaction_session, analysis_version,
                                 evidence_item, pattern_group, controller_decision, workflow_checkpoint
  app/db/models_graph.py         node, edge, break_event, break_embedding
  app/graph/entitlement.py       visibility matrix + predicate builder
  app/graph/repository.py        GraphRepository: resolve_book, book_context, lineage, similar_breaks
  app/graph/queries/postgres.py  dialect-specific SQL (recursive CTE)
  app/recon/checks.py            cause checks C1-C6
  app/recon/service.py           POST /recon/cause-checks contract
  app/workflow/state.py          InvestigationState + typed dicts
  app/workflow/nodes/resolve.py  one file per node
  app/workflow/nodes/gather.py
  app/workflow/nodes/group.py
  app/workflow/nodes/rank.py
  app/workflow/nodes/draft.py
  app/workflow/nodes/validate.py
  app/workflow/nodes/record.py
  app/workflow/nodes/escalate.py
  app/workflow/graph.py          wiring, interrupt_before, checkpointer
  api/main.py                    app factory, lifespan
  api/routes/runs.py             run schedule + rollups
  api/routes/sessions.py         open / resume / list
  api/routes/breaks.py           break population, paged
  api/websocket/handler.py       run.progress emitter
  fixtures/loader.py             seeds graph + breaks + priors
  fixtures/data/*.json|csv       fixture payloads
packages/contracts/
  build.py                       Pydantic -> JSON Schema -> .d.ts
apps/console/
  src/app/fobo/page.js           Control Tower
  src/app/fobo/layout.js
  src/components/fobo/shell/     TopBar, ControlTowerShell
  src/components/fobo/schedule/  RunScheduleCard, StatChipRow, ScheduleTimeline
  src/components/fobo/regions/   RegionRail, RecRow
  src/components/fobo/pipeline/  PipelineRail, StageNode, StackedProgress
  src/store/foboRunStore.js
  src/store/foboSessionStore.js
  src/hooks/useRunStream.js
  src/lib/WebSocketClient.js
  src/lib/apiClient.js
  src/styles/tokens.css          generated from docs/design/mock-tokens.css
docker-compose.yml
```

Split by responsibility, not layer: one file per workflow node, because nodes change independently and each carries its own test.

---

### Task 1: Repo scaffold, Postgres, and the contracts package

**Files:**
- Create: `docker-compose.yml`, `apps/api/pyproject.toml`, `apps/api/app/contracts/models.py`, `packages/contracts/build.py`, `.gitignore`
- Test: `apps/api/tests/test_contracts.py`

**Interfaces:**
- Consumes: nothing
- Produces: `WsEvent` union and the entity models every later task imports from `app.contracts.models`. Names: `RunProgress`, `ApprovalRequired`, `EvidenceRegistered`, `AnalysisVersionEvent`, `DecisionRecorded`, `ErrorEvent`, `BreakRecord`, `CandidateCause`, `PatternGroup`, `Caller`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_contracts.py`:

```python
import json
from pathlib import Path

from app.contracts.models import Caller, BreakRecord, RunProgress, WS_EVENT_MODELS


def test_caller_requires_entity_scope():
    c = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE1"], region="APAC")
    assert c.entity_scope == ["LE1"]


def test_every_ws_event_declares_a_literal_type():
    for model in WS_EVENT_MODELS:
        schema = model.model_json_schema()
        assert "type" in schema["properties"], f"{model.__name__} has no type field"
        assert "const" in schema["properties"]["type"], f"{model.__name__} type is not a literal"


def test_run_progress_round_trips_through_json_schema():
    evt = RunProgress(
        session_id="s1", node="gather", breaks_processed=3, breaks_total=14
    )
    payload = json.loads(evt.model_dump_json())
    assert RunProgress.model_validate(payload) == evt


def test_break_record_rejects_unknown_fields():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BreakRecord(
            break_id="b1", book_ref="APAC-CASH-01", line_code="CASH",
            cob_date="2026-08-03", fo_value=1.0, bo_value=2.0, surprise=True,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.contracts'`

- [ ] **Step 3: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: fobo
      POSTGRES_PASSWORD: fobo
      POSTGRES_DB: fobo
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fobo"]
      interval: 5s
      retries: 10
    volumes:
      - fobo_pg:/var/lib/postgresql/data

volumes:
  fobo_pg:
```

- [ ] **Step 4: Write `apps/api/pyproject.toml`**

```toml
[project]
name = "fobo-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "pgvector>=0.3",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
  "langgraph==0.2.45",
  "langgraph-checkpoint-postgres==2.0.2",
  "duckdb>=1.1",
  "pandas>=2.2",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "anyio>=4.4"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
```

- [ ] **Step 5: Write `apps/api/app/contracts/models.py`**

```python
"""Single source of truth for the event and entity contract.

Generated into JSON Schema and .d.ts by packages/contracts/build.py.
The console validates inbound events against the generated schema.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- entities ----------

class Caller(Strict):
    staff_id: str
    roles: list[str]
    entity_scope: list[str]
    region: str


class BreakRecord(Strict):
    break_id: str
    book_ref: str
    line_code: str
    cob_date: date
    fo_value: float | None = None
    bo_value: float | None = None


class CandidateCause(Strict):
    check_id: Literal["C1", "C2", "C3", "C4", "C5", "C6"]
    description: str
    estimated_value: float | None = None
    supporting_ids: list[str] = Field(default_factory=list)
    positive: bool


class PatternGroup(Strict):
    group_id: str
    pattern_code: str
    label: str
    mode: Literal["auto", "manual"]
    break_ids: list[str]
    historical_approval_rate: float | None = None


class AnalysisDraft(Strict):
    what_happened: str
    why: str
    what_to_do: str
    risk: str
    confidence_basis: str


# ---------- websocket events ----------

class RunProgress(Strict):
    type: Literal["run.progress"] = "run.progress"
    session_id: str
    node: str
    breaks_processed: int
    breaks_total: int


class ApprovalRequired(Strict):
    type: Literal["approval.required"] = "approval.required"
    session_id: str
    group_id: str
    pattern_code: str
    break_ids: list[str]
    historical_approval_rate: float | None = None


class EvidenceRegistered(Strict):
    type: Literal["evidence.registered"] = "evidence.registered"
    session_id: str
    evidence_id: str
    source_application: str
    retrieved_ts: datetime
    is_original_analysis: bool


class AnalysisVersionEvent(Strict):
    type: Literal["analysis.version"] = "analysis.version"
    session_id: str
    analysis_version_id: str
    supersedes: str | None = None


class DecisionRecorded(Strict):
    type: Literal["decision.recorded"] = "decision.recorded"
    session_id: str
    decision_id: str
    action: Literal["approve", "reject", "escalate"]
    reason: str | None = None
    idempotency_key: str


class ErrorEvent(Strict):
    type: Literal["error"] = "error"
    session_id: str | None = None
    code: str
    message: str
    application: str | None = None
    recoverable: bool


WS_EVENT_MODELS = [
    RunProgress, ApprovalRequired, EvidenceRegistered,
    AnalysisVersionEvent, DecisionRecorded, ErrorEvent,
]

WsEvent = Annotated[
    Union[
        RunProgress, ApprovalRequired, EvidenceRegistered,
        AnalysisVersionEvent, DecisionRecorded, ErrorEvent,
    ],
    Field(discriminator="type"),
]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/api && python -m pytest tests/test_contracts.py -v`
Expected: PASS, 4 tests

- [ ] **Step 7: Write the codegen script `packages/contracts/build.py`**

```python
"""Emit JSON Schema + .d.ts from the Pydantic contract."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.contracts.models import WS_EVENT_MODELS  # noqa: E402

OUT = Path(__file__).parent / "dist"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for model in WS_EVENT_MODELS:
        schema = model.model_json_schema()
        path = OUT / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2))
        subprocess.run(
            ["npx", "-y", "json-schema-to-typescript", str(path),
             "-o", str(OUT / f"{model.__name__}.d.ts")],
            check=True,
        )
    print(f"wrote {len(WS_EVENT_MODELS)} schemas to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
node_modules/
.next/
packages/contracts/dist/
.env
.env.*
```

- [ ] **Step 9: Verify Postgres comes up**

Run: `docker compose up -d postgres && docker compose ps`
Expected: `postgres` healthy, port `5433` bound

- [ ] **Step 10: Commit**

```bash
git add docker-compose.yml apps/api packages/contracts .gitignore
git commit -m "feat: scaffold api, postgres and the generated contract package"
```

---

### Task 2: Database schema and migrations

**Files:**
- Create: `apps/api/app/db/base.py`, `apps/api/app/db/models_session.py`, `apps/api/app/db/models_graph.py`, `apps/api/alembic.ini`, `apps/api/migrations/env.py`, `apps/api/migrations/versions/0001_initial.py`
- Test: `apps/api/tests/test_schema.py`

**Interfaces:**
- Consumes: `app.contracts.models` (Task 1)
- Produces: `Base`, `get_session()`, and ORM classes `InvestigationSession`, `AnalysisVersion`, `EvidenceItem`, `PatternGroupRow`, `ControllerDecision`, `Node`, `Edge`, `BreakEvent`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_schema.py`:

```python
import pytest
from sqlalchemy import select

from app.db.base import get_session
from app.db.models_graph import Node
from app.db.models_session import InvestigationSession


async def test_node_requires_legal_entity_id():
    """legal_entity_id is a first-class column, not a JSONB path,
    because the entitlement predicate filters on it in every query."""
    cols = Node.__table__.columns
    assert "legal_entity_id" in cols
    assert cols["legal_entity_id"].nullable is False


async def test_node_is_bitemporal():
    cols = Node.__table__.columns
    for name in ("valid_from", "valid_to", "recorded_from", "recorded_to"):
        assert name in cols, f"node is missing {name}"


async def test_break_event_is_not_bitemporal():
    """A break is an event that happened, not a fact whose validity changes."""
    from app.db.models_graph import BreakEvent
    assert "valid_from" not in BreakEvent.__table__.columns


async def test_can_insert_and_read_a_session():
    async with get_session() as s:
        s.add(InvestigationSession(
            investigation_session_id="sess-1",
            reconciliation_id="R-1055",
            master_book="APAC-CASH",
            business_date="2026-08-03",
            run_id="run-1100",
            status="analysing",
        ))
        await s.commit()
        got = await s.scalar(
            select(InvestigationSession).where(
                InvestigationSession.investigation_session_id == "sess-1"
            )
        )
        assert got.reconciliation_id == "R-1055"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write `apps/api/app/db/base.py`**

```python
import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "FOBO_DATABASE_URL", "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_session():
    async with SessionFactory() as session:
        yield session
```

- [ ] **Step 4: Write `apps/api/app/db/models_graph.py`**

```python
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Node(Base):
    __tablename__ = "node"
    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32))
    natural_key: Mapped[str] = mapped_column(String(128))
    legal_entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_node_type_key", "node_type", "natural_key"),
        Index("idx_node_entity", "legal_entity_id", "node_type"),
    )


class Edge(Base):
    __tablename__ = "edge"
    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    to_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    edge_type: Mapped[str] = mapped_column(String(32))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_edge_from", "from_node_id", "edge_type", "valid_from", "valid_to"),
        Index("idx_edge_to", "to_node_id", "edge_type", "valid_from", "valid_to"),
    )


class BreakEvent(Base):
    """Event layer. Deliberately not bitemporal."""
    __tablename__ = "break_event"
    break_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    line_code: Mapped[str] = mapped_column(String(32))
    cob_date: Mapped[date] = mapped_column(Date)
    fo_value: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    bo_value: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    delta: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    pattern_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_similar_breaks", "book_id", "line_code", "cob_date"),)


class BreakEmbedding(Base):
    __tablename__ = "break_embedding"
    break_id: Mapped[str] = mapped_column(String(64), ForeignKey("break_event.break_id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    model_identifier: Mapped[str] = mapped_column(String(64))
    embedded_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Write `apps/api/app/db/models_session.py`**

```python
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvestigationSession(Base):
    __tablename__ = "investigation_session"
    investigation_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reconciliation_id: Mapped[str] = mapped_column(String(64))
    master_book: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date] = mapped_column(Date)
    run_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisVersion(Base):
    __tablename__ = "analysis_version"
    analysis_version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    supersedes: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB)
    confidence_tier: Mapped[str] = mapped_column(String(16))
    prompt_version: Mapped[str] = mapped_column(String(32))
    skill_version: Mapped[str] = mapped_column(String(32))
    model_identifier: Mapped[str] = mapped_column(String(64))
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceItem(Base):
    __tablename__ = "evidence_item"
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    source_application: Mapped[str] = mapped_column(String(32))
    storage_mode: Mapped[str] = mapped_column(String(16))
    reference_uri: Mapped[str] = mapped_column(Text)
    integrity_hash: Mapped[str] = mapped_column(String(64))
    is_original_analysis: Mapped[bool] = mapped_column(Boolean)
    retrieved_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PatternGroupRow(Base):
    __tablename__ = "pattern_group"
    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    pattern_code: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(8))
    break_ids: Mapped[list] = mapped_column(JSONB)
    historical_approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class ControllerDecision(Base):
    __tablename__ = "controller_decision"
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    group_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("pattern_group.group_id"), nullable=True
    )
    controller_user_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    decided_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_decision_idem", "idempotency_key", unique=True),)
```

- [ ] **Step 6: Create the Alembic migration**

Run:
```bash
cd apps/api && alembic init -t async migrations
```

Then in `migrations/env.py`, replace the `target_metadata = None` line with:

```python
from app.db.base import Base
from app.db import models_graph, models_session  # noqa: F401  register tables
target_metadata = Base.metadata
```

And set in `alembic.ini`:
```
sqlalchemy.url = postgresql+asyncpg://fobo:fobo@localhost:5433/fobo
```

- [ ] **Step 7: Generate and apply the migration**

Run:
```bash
cd apps/api && alembic revision --autogenerate -m "initial" && alembic upgrade head
```

The generated migration must have `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` as its first upgrade statement — add it by hand if autogenerate omitted it.

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_schema.py -v`
Expected: PASS, 4 tests

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/db apps/api/migrations apps/api/alembic.ini apps/api/tests/test_schema.py
git commit -m "feat: bitemporal graph and session schema with alembic migration"
```

---

### Task 3: Fixture loader

**Files:**
- Create: `apps/api/fixtures/loader.py`, `apps/api/fixtures/data/reference_graph.json`, `apps/api/fixtures/data/breaks_small.json`, `apps/api/fixtures/data/prior_resolutions.json`
- Test: `apps/api/tests/test_fixtures.py`

**Interfaces:**
- Consumes: ORM models (Task 2)
- Produces: `load_all(session)` — seeds the graph and break population. Later tasks call it in test setup.

**Fixture contract (from the spec):** the small population is the mock's 14 breaks across `APAC-CASH-01`…`12`, producing exactly four pattern groups: `P-204` (6 books), `CPTY-REF` (3), `LATE-BOOK` (3), `DUP-SETTLE` (2). `APAC-CASH-07` appears in two groups and `APAC-CASH-09` twice in one. Prior history holds 42 `P-204` resolutions at 88% approval.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_fixtures.py`:

```python
from datetime import date

from sqlalchemy import func, select

from app.db.base import get_session
from app.db.models_graph import BreakEvent, Edge, Node
from fixtures.loader import load_all


async def test_loads_fourteen_breaks():
    async with get_session() as s:
        await load_all(s)
        n = await s.scalar(select(func.count()).select_from(BreakEvent))
        assert n == 14


async def test_a_book_hierarchy_changes_mid_period():
    """Proves as_of correctness is testable: one book moved desk on 2026-07-01."""
    async with get_session() as s:
        await load_all(s)
        rows = (await s.scalars(
            select(Edge).where(
                Edge.from_node_id == "book:APAC-CASH-05", Edge.edge_type == "BELONGS_TO"
            )
        )).all()
        assert len(rows) == 2, "expected a closed edge and an open one"
        closed = [r for r in rows if r.valid_to is not None]
        assert len(closed) == 1
        assert closed[0].valid_to == date(2026, 6, 30)


async def test_prior_resolutions_yield_the_mock_approval_rate():
    async with get_session() as s:
        await load_all(s)
        priors = (await s.scalars(
            select(BreakEvent).where(BreakEvent.pattern_code == "P-204",
                                     BreakEvent.outcome.isnot(None))
        )).all()
        assert len(priors) == 42
        approved = [p for p in priors if p.outcome == "approved"]
        assert round(len(approved) / len(priors), 2) == 0.88


async def test_every_node_has_a_legal_entity():
    async with get_session() as s:
        await load_all(s)
        n = await s.scalar(
            select(func.count()).select_from(Node).where(Node.legal_entity_id.is_(None))
        )
        assert n == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fixtures.loader'`

- [ ] **Step 3: Write `apps/api/fixtures/data/breaks_small.json`**

The 14 breaks and their expected pattern. `expected_pattern` is asserted by Task 7's test — it is the fixture's contract with the grouping logic.

```json
[
  {"break_id":"b-01","book_ref":"APAC-CASH-01","line_code":"CASH","fo_value":102340.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-02","book_ref":"APAC-CASH-02","line_code":"CASH","fo_value":101880.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-03","book_ref":"APAC-CASH-03","line_code":"CASH","fo_value":106120.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-04","book_ref":"APAC-CASH-04","line_code":"CASH","fo_value":100940.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-05","book_ref":"APAC-CASH-05","line_code":"CASH","fo_value":103470.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-06","book_ref":"APAC-CASH-06","line_code":"CASH","fo_value":101215.0,"bo_value":100000.0,"expected_pattern":"P-204","cause":"C1"},
  {"break_id":"b-07","book_ref":"APAC-CASH-07","line_code":"CASH","fo_value":118760.0,"bo_value":100000.0,"expected_pattern":"CPTY-REF","cause":"C2"},
  {"break_id":"b-08","book_ref":"APAC-CASH-08","line_code":"CASH","fo_value":107310.0,"bo_value":100000.0,"expected_pattern":"CPTY-REF","cause":"C2"},
  {"break_id":"b-09","book_ref":"APAC-CASH-11","line_code":"CASH","fo_value":102905.0,"bo_value":100000.0,"expected_pattern":"CPTY-REF","cause":"C2"},
  {"break_id":"b-10","book_ref":"APAC-CASH-09","line_code":"CASH","fo_value":109500.0,"bo_value":100000.0,"expected_pattern":"LATE-BOOK","cause":"C5"},
  {"break_id":"b-11","book_ref":"APAC-CASH-09","line_code":"CASH","fo_value":103220.0,"bo_value":100000.0,"expected_pattern":"LATE-BOOK","cause":"C5"},
  {"break_id":"b-12","book_ref":"APAC-CASH-10","line_code":"CASH","fo_value":105780.0,"bo_value":100000.0,"expected_pattern":"LATE-BOOK","cause":"C5"},
  {"break_id":"b-13","book_ref":"APAC-CASH-07","line_code":"CASH","fo_value":104020.0,"bo_value":100000.0,"expected_pattern":"DUP-SETTLE","cause":"C6"},
  {"break_id":"b-14","book_ref":"APAC-CASH-12","line_code":"CASH","fo_value":101640.0,"bo_value":100000.0,"expected_pattern":"DUP-SETTLE","cause":"C6"}
]
```

- [ ] **Step 4: Write `apps/api/fixtures/loader.py`**

```python
"""Seeds the graph and break population.

Reference rows are written the way ingestion writes them: a change closes the
existing edge and inserts a new one. Never updated in place.
"""
import json
import random
from datetime import date
from pathlib import Path

from sqlalchemy import delete

from app.db.models_graph import BreakEvent, Edge, Node

DATA = Path(__file__).parent / "data"
COB = date(2026, 8, 3)
ENTITY = "LE-APAC-01"

BOOKS = [f"APAC-CASH-{i:02d}" for i in range(1, 13)]


async def load_all(session) -> None:
    await _clear(session)
    await _load_reference_graph(session)
    await _load_breaks(session)
    await _load_priors(session)
    await session.commit()


async def _clear(session) -> None:
    for model in (BreakEvent, Edge, Node):
        await session.execute(delete(model))


async def _load_reference_graph(session) -> None:
    session.add(Node(
        node_id="desk:APAC-CASH", node_type="Desk", natural_key="APAC-CASH",
        legal_entity_id=ENTITY, valid_from=date(2020, 1, 1),
    ))
    session.add(Node(
        node_id="desk:APAC-TREASURY", node_type="Desk", natural_key="APAC-TREASURY",
        legal_entity_id=ENTITY, valid_from=date(2020, 1, 1),
    ))
    for book in BOOKS:
        session.add(Node(
            node_id=f"book:{book}", node_type="Book", natural_key=book,
            legal_entity_id=ENTITY, valid_from=date(2020, 1, 1),
        ))
        # APAC-CASH-05 moved desk on 2026-07-01: the old edge is CLOSED, not updated.
        if book == "APAC-CASH-05":
            session.add(Edge(
                edge_id=f"e:{book}:old", from_node_id=f"book:{book}",
                to_node_id="desk:APAC-TREASURY", edge_type="BELONGS_TO",
                valid_from=date(2020, 1, 1), valid_to=date(2026, 6, 30),
            ))
            session.add(Edge(
                edge_id=f"e:{book}:new", from_node_id=f"book:{book}",
                to_node_id="desk:APAC-CASH", edge_type="BELONGS_TO",
                valid_from=date(2026, 7, 1), valid_to=None,
            ))
        else:
            session.add(Edge(
                edge_id=f"e:{book}", from_node_id=f"book:{book}",
                to_node_id="desk:APAC-CASH", edge_type="BELONGS_TO",
                valid_from=date(2020, 1, 1), valid_to=None,
            ))


async def _load_breaks(session) -> None:
    rows = json.loads((DATA / "breaks_small.json").read_text())
    for r in rows:
        session.add(BreakEvent(
            break_id=r["break_id"], book_id=f"book:{r['book_ref']}",
            line_code=r["line_code"], cob_date=COB,
            fo_value=r["fo_value"], bo_value=r["bo_value"],
            delta=r["fo_value"] - r["bo_value"],
        ))


async def _load_priors(session) -> None:
    """42 prior P-204 resolutions at exactly 88% approval (37 of 42)."""
    rng = random.Random(204)
    approved_count = round(0.88 * 42)  # 37
    outcomes = ["approved"] * approved_count + ["rejected"] * (42 - approved_count)
    rng.shuffle(outcomes)
    for i, outcome in enumerate(outcomes):
        session.add(BreakEvent(
            break_id=f"prior-p204-{i:03d}",
            book_id=f"book:{BOOKS[i % len(BOOKS)]}",
            line_code="CASH", cob_date=date(2026, 6, 1),
            fo_value=100000.0, bo_value=99000.0, delta=1000.0,
            pattern_code="P-204", outcome=outcome,
            narrative="Nostro statement received after the 23:30 cutoff.",
        ))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_fixtures.py -v`
Expected: PASS, 4 tests. `round(37/42, 2) == 0.88`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/fixtures apps/api/tests/test_fixtures.py
git commit -m "feat: fixture loader seeding graph, 14 breaks and 42 priors"
```

---

### Task 4: Graph repository and the entitlement predicate

**Files:**
- Create: `apps/api/app/graph/entitlement.py`, `apps/api/app/graph/repository.py`, `apps/api/app/graph/queries/postgres.py`, `apps/api/app/graph/errors.py`
- Test: `apps/api/tests/test_entitlement.py`, `apps/api/tests/test_repository.py`

**Interfaces:**
- Consumes: `load_all` (Task 3), `Caller` (Task 1)
- Produces:
  - `visible_node_types(roles: list[str]) -> set[str]`
  - `build_entitlement_predicate(caller: Caller)` returning a SQLAlchemy boolean clause
  - `GraphRepository.resolve_book(book_ref: str, as_of: date, caller: Caller) -> str` (returns `node_id`)
  - `GraphRepository.book_context(book_id: str, as_of: date, caller: Caller) -> dict`
  - `GraphRepository.similar_breaks(book_id, line_code, cob_date, lookback, caller) -> list[dict]`
  - Exceptions `UnresolvedBook`, `AmbiguousBook`

- [ ] **Step 1: Write the failing entitlement test**

Create `apps/api/tests/test_entitlement.py`:

```python
import pytest

from app.contracts.models import Caller
from app.graph.entitlement import visible_node_types

MATRIX = {
    "Trade":         {"FO", "PC", "RISK"},
    "Position":      {"FO", "RISK"},
    "LedgerEntry":   {"BO", "PC", "REG"},
    "StaticMapping": {"BO", "REG"},
    "Adjustment":    {"BO", "PC"},
    "RiskRun":       {"FO", "RISK"},
    "Job":           {"FO", "BO", "PC"},
    "Book":          {"FO", "BO", "PC", "REG", "RISK"},
    "Desk":          {"FO", "BO", "PC", "REG", "RISK"},
}


@pytest.mark.parametrize("role", ["FO", "BO", "PC", "REG", "RISK"])
def test_visibility_matrix_matches_the_spec(role):
    visible = visible_node_types([role])
    expected = {nt for nt, roles in MATRIX.items() if role in roles}
    assert visible == expected


def test_a_back_office_caller_cannot_see_trades():
    assert "Trade" not in visible_node_types(["BO"])


def test_a_front_office_caller_cannot_see_ledger_entries():
    assert "LedgerEntry" not in visible_node_types(["FO"])


def test_roles_union():
    assert "Trade" in visible_node_types(["BO", "FO"])
    assert "LedgerEntry" in visible_node_types(["BO", "FO"])


def test_unknown_role_grants_nothing():
    assert visible_node_types(["NOBODY"]) == set()
```

- [ ] **Step 2: Write the failing repository test**

Create `apps/api/tests/test_repository.py`:

```python
from datetime import date

import pytest

from app.contracts.models import Caller
from app.db.base import get_session
from app.graph.errors import UnresolvedBook
from app.graph.repository import GraphRepository
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
OUTSIDER = Caller(staff_id="p2", roles=["FO"], entity_scope=["LE-EMEA-01"], region="EMEA")


async def test_resolves_a_book():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        assert await repo.resolve_book("APAC-CASH-01", date(2026, 8, 3), FO) == "book:APAC-CASH-01"


async def test_unknown_book_raises_rather_than_guessing():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        with pytest.raises(UnresolvedBook):
            await repo.resolve_book("NOPE-01", date(2026, 8, 3), FO)


async def test_a_caller_outside_the_entity_scope_cannot_resolve():
    """Entitlement is enforced in the query, so this is indistinguishable
    from the book not existing."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        with pytest.raises(UnresolvedBook):
            await repo.resolve_book("APAC-CASH-01", date(2026, 8, 3), OUTSIDER)


async def test_as_of_returns_the_hierarchy_in_force_on_that_date():
    """APAC-CASH-05 moved from APAC-TREASURY to APAC-CASH on 2026-07-01."""
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        before = await repo.book_context("book:APAC-CASH-05", date(2026, 6, 15), FO)
        after = await repo.book_context("book:APAC-CASH-05", date(2026, 8, 3), FO)
        assert before["desk"] == "APAC-TREASURY"
        assert after["desk"] == "APAC-CASH"


async def test_similar_breaks_returns_priors_for_the_book():
    async with get_session() as s:
        await load_all(s)
        repo = GraphRepository(s)
        priors = await repo.similar_breaks(
            "book:APAC-CASH-01", "CASH", date(2026, 8, 3), 180, FO
        )
        assert len(priors) > 0
        assert all(p["pattern_code"] == "P-204" for p in priors)
```

- [ ] **Step 3: Run both tests to verify they fail**

Run: `cd apps/api && python -m pytest tests/test_entitlement.py tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.graph'`

- [ ] **Step 4: Write `apps/api/app/graph/entitlement.py`**

```python
"""Role-based node visibility.

Enforced by injecting a predicate into every query before execution.
Post-filtering is prohibited: it leaks through counts and timing.
"""
from sqlalchemy import and_

from app.contracts.models import Caller
from app.db.models_graph import Node

VISIBILITY: dict[str, set[str]] = {
    "Trade":         {"FO", "PC", "RISK"},
    "Position":      {"FO", "RISK"},
    "LedgerEntry":   {"BO", "PC", "REG"},
    "StaticMapping": {"BO", "REG"},
    "Adjustment":    {"BO", "PC"},
    "RiskRun":       {"FO", "RISK"},
    "Job":           {"FO", "BO", "PC"},
    "Book":          {"FO", "BO", "PC", "REG", "RISK"},
    "Desk":          {"FO", "BO", "PC", "REG", "RISK"},
}


def visible_node_types(roles: list[str]) -> set[str]:
    return {nt for nt, allowed in VISIBILITY.items() if allowed & set(roles)}


def build_entitlement_predicate(caller: Caller):
    return and_(
        Node.node_type.in_(visible_node_types(caller.roles)),
        Node.legal_entity_id.in_(caller.entity_scope),
    )
```

- [ ] **Step 5: Write `apps/api/app/graph/errors.py`**

```python
class UnresolvedBook(Exception):
    """Zero matches. Escalates UNRESOLVED_BOOK."""


class AmbiguousBook(Exception):
    """More than one match. Escalates AMBIGUOUS_BOOK. Never auto-pick."""
```

- [ ] **Step 6: Write `apps/api/app/graph/queries/postgres.py`**

```python
"""Dialect-specific SQL. An Oracle variant lands beside this file
without touching repository callers."""

from sqlalchemy import text

LINEAGE_CTE = text("""
WITH RECURSIVE lineage(node_id, depth) AS (
    SELECT e.to_node_id, 0
    FROM edge e
    WHERE e.from_node_id = :book_id
      AND e.edge_type = :edge_type
      AND e.valid_from <= :as_of
      AND (e.valid_to IS NULL OR e.valid_to >= :as_of)
    UNION ALL
    SELECT e.to_node_id, l.depth + 1
    FROM edge e
    JOIN lineage l ON e.from_node_id = l.node_id
    WHERE l.depth < :max_depth
      AND e.valid_from <= :as_of
      AND (e.valid_to IS NULL OR e.valid_to >= :as_of)
)
SELECT node_id, depth FROM lineage
""")
```

- [ ] **Step 7: Write `apps/api/app/graph/repository.py`**

```python
"""Graph repository. Every method takes as_of and caller.

Neither is optional and neither has a default — a method that could be
called without them would eventually be called without them.
"""
from datetime import date, timedelta

from sqlalchemy import and_, or_, select

from app.contracts.models import Caller
from app.db.models_graph import BreakEvent, Edge, Node
from app.graph.entitlement import build_entitlement_predicate
from app.graph.errors import AmbiguousBook, UnresolvedBook
from app.graph.queries.postgres import LINEAGE_CTE


def _valid_at(model, as_of: date):
    return and_(
        model.valid_from <= as_of,
        or_(model.valid_to.is_(None), model.valid_to >= as_of),
    )


class GraphRepository:
    def __init__(self, session):
        self._s = session

    async def resolve_book(self, book_ref: str, as_of: date, caller: Caller) -> str:
        rows = (await self._s.scalars(
            select(Node).where(
                Node.node_type == "Book",
                Node.natural_key == book_ref,
                _valid_at(Node, as_of),
                build_entitlement_predicate(caller),
            )
        )).all()
        if not rows:
            raise UnresolvedBook(book_ref)
        if len(rows) > 1:
            raise AmbiguousBook(f"{book_ref} resolved to {len(rows)} nodes")
        return rows[0].node_id

    async def book_context(self, book_id: str, as_of: date, caller: Caller) -> dict:
        desk_id = await self._s.scalar(
            select(Edge.to_node_id).where(
                Edge.from_node_id == book_id,
                Edge.edge_type == "BELONGS_TO",
                _valid_at(Edge, as_of),
            )
        )
        desk = await self._s.scalar(
            select(Node).where(
                Node.node_id == desk_id,
                _valid_at(Node, as_of),
                build_entitlement_predicate(caller),
            )
        )
        return {
            "book_id": book_id,
            "desk": desk.natural_key if desk else None,
            "legal_entity_id": desk.legal_entity_id if desk else None,
            "as_of": as_of,
        }

    async def lineage(self, book_id: str, direction: str, depth: int,
                      as_of: date, caller: Caller) -> list[dict]:
        result = await self._s.execute(
            LINEAGE_CTE,
            {"book_id": book_id, "edge_type": direction,
             "as_of": as_of, "max_depth": min(depth, 4)},
        )
        candidates = {r.node_id: r.depth for r in result}
        if not candidates:
            return []
        visible = (await self._s.scalars(
            select(Node).where(
                Node.node_id.in_(candidates),
                _valid_at(Node, as_of),
                build_entitlement_predicate(caller),
            )
        )).all()
        return [{"node_id": n.node_id, "node_type": n.node_type,
                 "natural_key": n.natural_key, "depth": candidates[n.node_id]}
                for n in visible]

    async def similar_breaks(self, book_id: str, line_code: str, cob_date: date,
                             lookback: int, caller: Caller) -> list[dict]:
        """Structural query first: it bounds the candidate set.
        pgvector reranks within this set in Phase 3 — never widens it."""
        floor = cob_date - timedelta(days=lookback)
        rows = (await self._s.scalars(
            select(BreakEvent).join(Node, Node.node_id == BreakEvent.book_id).where(
                BreakEvent.line_code == line_code,
                BreakEvent.cob_date >= floor,
                BreakEvent.cob_date < cob_date,
                BreakEvent.outcome.isnot(None),
                build_entitlement_predicate(caller),
            ).limit(20)
        )).all()
        return [{"break_id": r.break_id, "pattern_code": r.pattern_code,
                 "outcome": r.outcome, "narrative": r.narrative,
                 "cob_date": r.cob_date} for r in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_entitlement.py tests/test_repository.py -v`
Expected: PASS, 10 tests

- [ ] **Step 9: Commit**

```bash
git add apps/api/app/graph apps/api/tests/test_entitlement.py apps/api/tests/test_repository.py
git commit -m "feat: graph repository with entitlement predicate and as_of correctness"
```

---

### Task 5: Cause checks C1–C6

**Files:**
- Create: `apps/api/app/recon/checks.py`, `apps/api/app/recon/service.py`
- Test: `apps/api/tests/test_recon.py`

**Interfaces:**
- Consumes: `CandidateCause` (Task 1)
- Produces: `run_cause_checks(snapshot: dict) -> list[CandidateCause]` — returns **all six**, including negatives.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_recon.py`:

```python
from app.recon.checks import run_cause_checks

BASE = {
    "break_id": "b-01",
    "fo_booking_ts": "2026-08-03T22:00:00Z",
    "bo_cutoff_ts": "2026-08-03T23:30:00Z",
    "mapping_present": True,
    "fo_dataset_id": "EOD-2026-08-03",
    "bo_dataset_id": "EOD-2026-08-03",
    "fo_components": ["principal"],
    "bo_components": ["principal"],
    "fo_version": 1,
    "bo_version": 1,
    "fo_adjustments": [],
    "bo_adjustments": [],
}


def test_returns_all_six_checks_including_negatives():
    out = run_cause_checks(BASE)
    assert len(out) == 6
    assert [c.check_id for c in out] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert all(c.positive is False for c in out)


def test_c1_fires_when_booking_is_after_the_cutoff():
    snap = BASE | {"fo_booking_ts": "2026-08-04T00:15:00Z"}
    c1 = next(c for c in run_cause_checks(snap) if c.check_id == "C1")
    assert c1.positive is True


def test_c2_fires_when_the_mapping_is_missing():
    c2 = next(c for c in run_cause_checks(BASE | {"mapping_present": False})
              if c.check_id == "C2")
    assert c2.positive is True


def test_c3_fires_on_different_datasets():
    c3 = next(c for c in run_cause_checks(BASE | {"bo_dataset_id": "EOD-2026-08-02"})
              if c.check_id == "C3")
    assert c3.positive is True


def test_c4_fires_when_a_component_is_one_sided():
    c4 = next(c for c in run_cause_checks(BASE | {"fo_components": ["principal", "fee"]})
              if c.check_id == "C4")
    assert c4.positive is True


def test_c5_fires_on_version_mismatch():
    c5 = next(c for c in run_cause_checks(BASE | {"fo_version": 2}) if c.check_id == "C5")
    assert c5.positive is True


def test_c6_fires_on_a_one_sided_adjustment():
    c6 = next(c for c in run_cause_checks(BASE | {"bo_adjustments": ["manual-1"]})
              if c.check_id == "C6")
    assert c6.positive is True


def test_is_deterministic():
    """Same snapshot in, byte-identical output out."""
    a = [c.model_dump_json() for c in run_cause_checks(BASE)]
    b = [c.model_dump_json() for c in run_cause_checks(BASE)]
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_recon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.recon'`

- [ ] **Step 3: Write `apps/api/app/recon/checks.py`**

```python
"""The six cause checks.

The architecture doc places these in a Java Spring Boot service. This is a
Python stand-in behind the same HTTP contract, so the Java service can
replace it without touching callers.

Pure functions over dated snapshots: the same (book, cob_date,
snapshot_version) must produce identical output.
"""
from datetime import datetime

from app.contracts.models import CandidateCause


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _c1(s: dict) -> CandidateCause:
    late = _ts(s["fo_booking_ts"]) > _ts(s["bo_cutoff_ts"])
    return CandidateCause(
        check_id="C1", positive=late,
        description="FO booking timestamp is after the BO ledger cut-off"
        if late else "FO booking is within the BO cut-off",
        supporting_ids=[s["break_id"]] if late else [],
    )


def _c2(s: dict) -> CandidateCause:
    missing = not s["mapping_present"]
    return CandidateCause(
        check_id="C2", positive=missing,
        description="Static mapping missing or newly effective"
        if missing else "Static mapping present",
        supporting_ids=[s["break_id"]] if missing else [],
    )


def _c3(s: dict) -> CandidateCause:
    differs = s["fo_dataset_id"] != s["bo_dataset_id"]
    return CandidateCause(
        check_id="C3", positive=differs,
        description="FO and BO reference different rate or curve datasets"
        if differs else "FO and BO reference the same dataset",
        supporting_ids=[s["break_id"]] if differs else [],
    )


def _c4(s: dict) -> CandidateCause:
    one_sided = set(s["fo_components"]) ^ set(s["bo_components"])
    return CandidateCause(
        check_id="C4", positive=bool(one_sided),
        description=f"Components present on one side only: {sorted(one_sided)}"
        if one_sided else "Components match on both sides",
        supporting_ids=[s["break_id"]] if one_sided else [],
    )


def _c5(s: dict) -> CandidateCause:
    mismatch = s["fo_version"] != s["bo_version"]
    return CandidateCause(
        check_id="C5", positive=mismatch,
        description="Trade version mismatch across snapshots"
        if mismatch else "Trade versions match",
        supporting_ids=[s["break_id"]] if mismatch else [],
    )


def _c6(s: dict) -> CandidateCause:
    one_sided = set(s["fo_adjustments"]) ^ set(s["bo_adjustments"])
    return CandidateCause(
        check_id="C6", positive=bool(one_sided),
        description="Adjustment applied on one side, absent on the other"
        if one_sided else "Adjustments match on both sides",
        supporting_ids=[s["break_id"]] if one_sided else [],
    )


CHECKS = (_c1, _c2, _c3, _c4, _c5, _c6)


def run_cause_checks(snapshot: dict) -> list[CandidateCause]:
    """All six run and all six results are returned, negatives included."""
    return [check(snapshot) for check in CHECKS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_recon.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/recon apps/api/tests/test_recon.py
git commit -m "feat: six deterministic cause checks returning negatives"
```

---

### Task 6: Workflow state, resolve and gather

**Files:**
- Create: `apps/api/app/workflow/state.py`, `apps/api/app/workflow/nodes/resolve.py`, `apps/api/app/workflow/nodes/gather.py`, `apps/api/app/workflow/nodes/escalate.py`
- Test: `apps/api/tests/test_nodes_resolve_gather.py`

**Interfaces:**
- Consumes: `GraphRepository` (Task 4), `run_cause_checks` (Task 5)
- Produces:
  - `InvestigationState` TypedDict
  - `async def resolve(state: InvestigationState) -> dict` — returns a partial state update
  - `async def gather(state: InvestigationState) -> dict`
  - `async def escalate(state: InvestigationState) -> dict`
  - `MAX_HYPOTHESIS_ATTEMPTS = 3`, `MAX_REVIEW_CYCLES = 2`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_nodes_resolve_gather.py`:

```python
from datetime import date

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow.nodes.gather import gather
from app.workflow.nodes.resolve import resolve
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")


def _state(breaks):
    return {
        "investigation_session_id": "sess-1",
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": FO,
        "breaks": breaks,
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }


async def test_resolve_pins_as_of_to_the_business_date():
    async with get_session() as s:
        await load_all(s)
        st = _state([{"break_id": "b-01", "book_ref": "APAC-CASH-01"}])
        out = await resolve(st, session=s)
        assert out["book_resolutions"]["b-01"] == "book:APAC-CASH-01"
        assert out["as_of"] == date(2026, 8, 3)


async def test_resolve_escalates_an_unresolvable_book():
    async with get_session() as s:
        await load_all(s)
        st = _state([{"break_id": "b-x", "book_ref": "NOPE-01"}])
        out = await resolve(st, session=s)
        assert out["outcome"] == "escalated"
        assert out["escalation_reason"] == "UNRESOLVED_BOOK"


async def test_gather_returns_all_six_candidates_per_break():
    async with get_session() as s:
        await load_all(s)
        st = _state([{"break_id": "b-01", "book_ref": "APAC-CASH-01"}])
        st |= await resolve(st, session=s)
        out = await gather(st, session=s)
        assert len(out["candidates"]["b-01"]) == 6


async def test_gather_flags_evidence_gaps_rather_than_failing():
    """Priors unavailable degrades; it does not escalate."""
    async with get_session() as s:
        await load_all(s)
        st = _state([{"break_id": "b-01", "book_ref": "APAC-CASH-01"}])
        st |= await resolve(st, session=s)
        st["_force_priors_unavailable"] = True
        out = await gather(st, session=s)
        assert "priors:b-01" in out["evidence_gaps"]
        assert out.get("outcome") != "escalated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_nodes_resolve_gather.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workflow'`

- [ ] **Step 3: Write `apps/api/app/workflow/state.py`**

```python
from datetime import date
from typing import Any, TypedDict

from app.contracts.models import AnalysisDraft, Caller, CandidateCause, PatternGroup

MAX_HYPOTHESIS_ATTEMPTS = 3
MAX_REVIEW_CYCLES = 2


class InvestigationState(TypedDict, total=False):
    # Identity
    investigation_session_id: str
    reconciliation_id: str
    master_book: str
    business_date: date
    run_id: str
    caller: Caller

    # Population
    breaks: list[dict]
    book_resolutions: dict[str, str]
    as_of: date

    # Gather
    deltas: dict[str, float]
    candidates: dict[str, list[CandidateCause]]
    priors: dict[str, list[dict]]
    lineage: dict[str, list[dict]]
    evidence_gaps: list[str]

    # Group / rank / draft
    pattern_groups: list[PatternGroup]
    ranking: dict[str, Any]
    draft: AnalysisDraft | None
    validation_errors: list[str]
    hypothesis_attempts: int

    # Review
    review_cycles: int
    decisions: list[dict]

    # Outcome
    outcome: str | None
    escalation_reason: str | None
```

- [ ] **Step 4: Write `apps/api/app/workflow/nodes/resolve.py`**

```python
"""Resolve each break's book, pinned to as_of = business_date.

Zero matches escalates UNRESOLVED_BOOK. Multiple matches escalates
AMBIGUOUS_BOOK and never auto-picks.
"""
from app.graph.errors import AmbiguousBook, UnresolvedBook
from app.graph.repository import GraphRepository
from app.workflow.state import InvestigationState


async def resolve(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    as_of = state["business_date"]
    caller = state["caller"]
    resolutions: dict[str, str] = {}

    for brk in state["breaks"]:
        try:
            resolutions[brk["break_id"]] = await repo.resolve_book(
                brk["book_ref"], as_of, caller
            )
        except UnresolvedBook:
            return {"outcome": "escalated", "escalation_reason": "UNRESOLVED_BOOK",
                    "as_of": as_of, "book_resolutions": resolutions}
        except AmbiguousBook:
            return {"outcome": "escalated", "escalation_reason": "AMBIGUOUS_BOOK",
                    "as_of": as_of, "book_resolutions": resolutions}

    return {"book_resolutions": resolutions, "as_of": as_of}
```

- [ ] **Step 5: Write `apps/api/app/workflow/nodes/gather.py`**

```python
"""Fan out per break: delta, cause checks, lineage, priors.

Missing priors degrade and flag evidence_gaps.
Missing delta or cause checks escalate — there is nothing to explain.
"""
from app.graph.repository import GraphRepository
from app.recon.checks import run_cause_checks
from app.workflow.state import InvestigationState


def _snapshot(brk: dict) -> dict:
    """Builds the cause-check snapshot from the fixture break record.
    In Phase 3 this comes from the CATS and MOTIF adapters."""
    return {
        "break_id": brk["break_id"],
        "fo_booking_ts": brk.get("fo_booking_ts", "2026-08-03T22:00:00Z"),
        "bo_cutoff_ts": brk.get("bo_cutoff_ts", "2026-08-03T23:30:00Z"),
        "mapping_present": brk.get("mapping_present", True),
        "fo_dataset_id": brk.get("fo_dataset_id", "EOD-2026-08-03"),
        "bo_dataset_id": brk.get("bo_dataset_id", "EOD-2026-08-03"),
        "fo_components": brk.get("fo_components", ["principal"]),
        "bo_components": brk.get("bo_components", ["principal"]),
        "fo_version": brk.get("fo_version", 1),
        "bo_version": brk.get("bo_version", 1),
        "fo_adjustments": brk.get("fo_adjustments", []),
        "bo_adjustments": brk.get("bo_adjustments", []),
    }


async def gather(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    as_of = state["as_of"]
    caller = state["caller"]

    deltas, candidates, priors, lineage = {}, {}, {}, {}
    gaps = list(state.get("evidence_gaps", []))

    for brk in state["breaks"]:
        bid = brk["break_id"]
        book_id = state["book_resolutions"][bid]

        fo, bo = brk.get("fo_value"), brk.get("bo_value")
        if fo is None or bo is None:
            return {"outcome": "escalated", "escalation_reason": "DELTA_UNAVAILABLE"}
        deltas[bid] = fo - bo

        candidates[bid] = run_cause_checks(_snapshot(brk))
        if len(candidates[bid]) != 6:
            return {"outcome": "escalated", "escalation_reason": "CHECKS_UNAVAILABLE"}

        lineage[bid] = await repo.lineage(book_id, "BELONGS_TO", 4, as_of, caller)

        if state.get("_force_priors_unavailable"):
            priors[bid] = []
            gaps.append(f"priors:{bid}")
        else:
            priors[bid] = await repo.similar_breaks(
                book_id, brk.get("line_code", "CASH"), as_of, 180, caller
            )

    return {"deltas": deltas, "candidates": candidates,
            "priors": priors, "lineage": lineage, "evidence_gaps": gaps}
```

- [ ] **Step 6: Write `apps/api/app/workflow/nodes/escalate.py`**

```python
"""Terminal. Sets the reason code and preserves all gathered evidence."""
from app.workflow.state import InvestigationState

REASONS = {
    "UNRESOLVED_BOOK", "AMBIGUOUS_BOOK", "UNMAPPED_BOOK",
    "DELTA_UNAVAILABLE", "CHECKS_UNAVAILABLE",
    "RETRY_EXHAUSTED", "VALIDATION_FAILED",
}


async def escalate(state: InvestigationState) -> dict:
    reason = state.get("escalation_reason")
    if reason not in REASONS:
        raise ValueError(f"unknown escalation reason: {reason}")
    return {"outcome": "escalated", "escalation_reason": reason}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_nodes_resolve_gather.py -v`
Expected: PASS, 4 tests

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/workflow apps/api/tests/test_nodes_resolve_gather.py
git commit -m "feat: workflow state with resolve, gather and escalate nodes"
```

---

### Task 7: The `group` node

**Files:**
- Create: `apps/api/app/workflow/nodes/group.py`
- Test: `apps/api/tests/test_node_group.py`

**Interfaces:**
- Consumes: `gather` output (Task 6), `GraphRepository.similar_breaks` (Task 4)
- Produces: `async def group(state, *, session) -> dict` setting `pattern_groups: list[PatternGroup]`

**Why this node exists:** the mock's headline metric is "Decisions saved: 20 to 6". Neither source document has a step that performs the collapse. This is it, and it is the reason pgvector is in the stack. Phase 1 groups by cause-check signature and attaches the historical rate from `similar_breaks`; the pgvector rerank lands in Phase 3.

**Pattern codes** are assigned from the dominant positive check in the cluster:

| Dominant check | Pattern code | Label | Mode |
|---|---|---|---|
| C1 | `P-204` | FX timing lag | auto |
| C2 | `CPTY-REF` | Unmatched counterparty reference | manual |
| C5 | `LATE-BOOK` | Late trade booking | manual |
| C6 | `DUP-SETTLE` | Duplicate settlement suspected | manual |
| C3 | `VAL-DATASET` | Valuation dataset mismatch | manual |
| C4 | `COMP-ONESIDE` | One-sided component | manual |

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_node_group.py`:

```python
import json
from datetime import date
from pathlib import Path

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.resolve import resolve
from fixtures.loader import load_all

FIXTURE = Path(__file__).parents[1] / "fixtures" / "data" / "breaks_small.json"
FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}


def _breaks():
    rows = json.loads(FIXTURE.read_text())
    return [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in rows]


async def _run_to_group(session):
    st = {
        "investigation_session_id": "sess-1", "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH", "business_date": date(2026, 8, 3),
        "run_id": "run-1100", "caller": FO, "breaks": _breaks(),
        "book_resolutions": {}, "evidence_gaps": [],
        "hypothesis_attempts": 0, "review_cycles": 0,
    }
    st |= await resolve(st, session=session)
    st |= await gather(st, session=session)
    st |= await group(st, session=session)
    return st


async def test_fourteen_breaks_collapse_to_four_groups():
    """This is the 'decisions saved' lever. If this fails, the metric is a lie."""
    async with get_session() as s:
        await load_all(s)
        st = await _run_to_group(s)
        assert len(st["pattern_groups"]) == 4


async def test_group_sizes_match_the_mock():
    async with get_session() as s:
        await load_all(s)
        st = await _run_to_group(s)
        sizes = {g.pattern_code: len(g.break_ids) for g in st["pattern_groups"]}
        assert sizes == {"P-204": 6, "CPTY-REF": 3, "LATE-BOOK": 3, "DUP-SETTLE": 2}


async def test_p204_is_auto_and_the_rest_are_manual():
    async with get_session() as s:
        await load_all(s)
        st = await _run_to_group(s)
        modes = {g.pattern_code: g.mode for g in st["pattern_groups"]}
        assert modes["P-204"] == "auto"
        assert all(m == "manual" for c, m in modes.items() if c != "P-204")


async def test_p204_carries_the_historical_approval_rate():
    """Derived from the 42 priors, not hard-coded."""
    async with get_session() as s:
        await load_all(s)
        st = await _run_to_group(s)
        p204 = next(g for g in st["pattern_groups"] if g.pattern_code == "P-204")
        assert p204.historical_approval_rate == 0.88


async def test_every_break_lands_in_exactly_one_group():
    async with get_session() as s:
        await load_all(s)
        st = await _run_to_group(s)
        assigned = [b for g in st["pattern_groups"] for b in g.break_ids]
        assert len(assigned) == 14
        assert len(set(assigned)) == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_node_group.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workflow.nodes.group'`

- [ ] **Step 3: Write `apps/api/app/workflow/nodes/group.py`**

```python
"""Collapse breaks into pattern groups.

This node is the efficiency lever: 14 breaks become 4 decisions. It clusters
by cause-check signature, then attaches a pattern label and the historical
approval rate derived from prior resolutions.

Phase 3 adds a pgvector rerank against historical resolution narratives.
The structural clustering below stays the deterministic core.
"""
from collections import defaultdict

from app.contracts.models import PatternGroup
from app.workflow.state import InvestigationState

PATTERNS = {
    "C1": ("P-204", "FX timing lag", "auto"),
    "C2": ("CPTY-REF", "Unmatched counterparty reference", "manual"),
    "C3": ("VAL-DATASET", "Valuation dataset mismatch", "manual"),
    "C4": ("COMP-ONESIDE", "One-sided component", "manual"),
    "C5": ("LATE-BOOK", "Late trade booking", "manual"),
    "C6": ("DUP-SETTLE", "Duplicate settlement suspected", "manual"),
}

# Ties broken in check order, so grouping is deterministic.
CHECK_ORDER = ["C1", "C2", "C3", "C4", "C5", "C6"]


def _signature(candidates) -> str | None:
    """The dominant positive check. None means no cause was found."""
    positives = {c.check_id for c in candidates if c.positive}
    for check in CHECK_ORDER:
        if check in positives:
            return check
    return None


def _approval_rate(priors: list[dict], pattern_code: str) -> float | None:
    relevant = [p for p in priors if p["pattern_code"] == pattern_code]
    if not relevant:
        return None
    approved = [p for p in relevant if p["outcome"] == "approved"]
    return round(len(approved) / len(relevant), 2)


async def group(state: InvestigationState, *, session) -> dict:
    clusters: dict[str, list[str]] = defaultdict(list)
    for brk in state["breaks"]:
        bid = brk["break_id"]
        sig = _signature(state["candidates"][bid])
        if sig is None:
            clusters["UNGROUPED"].append(bid)
        else:
            clusters[sig].append(bid)

    all_priors = [p for plist in state.get("priors", {}).values() for p in plist]

    groups: list[PatternGroup] = []
    for check in CHECK_ORDER:
        if check not in clusters:
            continue
        code, label, mode = PATTERNS[check]
        groups.append(PatternGroup(
            group_id=f"{state['investigation_session_id']}:{code}",
            pattern_code=code, label=label, mode=mode,
            break_ids=clusters[check],
            historical_approval_rate=_approval_rate(all_priors, code),
        ))

    if "UNGROUPED" in clusters:
        groups.append(PatternGroup(
            group_id=f"{state['investigation_session_id']}:UNGROUPED",
            pattern_code="UNGROUPED", label="No cause identified", mode="manual",
            break_ids=clusters["UNGROUPED"], historical_approval_rate=None,
        ))

    return {"pattern_groups": groups}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_node_group.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/workflow/nodes/group.py apps/api/tests/test_node_group.py
git commit -m "feat: group node collapsing 14 breaks into 4 pattern decisions"
```

---

### Task 8: rank, draft and validate

**Files:**
- Create: `apps/api/app/workflow/nodes/rank.py`, `apps/api/app/workflow/nodes/draft.py`, `apps/api/app/workflow/nodes/validate.py`
- Test: `apps/api/tests/test_nodes_rank_draft_validate.py`

**Interfaces:**
- Consumes: `group` output (Task 7)
- Produces:
  - `async def rank(state, *, session) -> dict` setting `ranking`
  - `async def draft(state, *, session) -> dict` setting `draft: AnalysisDraft`
  - `async def validate(state, *, session) -> dict` setting `validation_errors`

**Phase 1 has no model call.** `rank` takes the deterministic fast path whenever there is exactly one positive candidate, which every fixture break has. Multi-candidate breaks record `needs_model` and are handled in Phase 3. `draft` renders a template over grounded values.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_nodes_rank_draft_validate.py`:

```python
from app.contracts.models import AnalysisDraft, CandidateCause, PatternGroup
from app.workflow.nodes.draft import draft
from app.workflow.nodes.rank import rank
from app.workflow.nodes.validate import validate


def _pos(check_id):
    return CandidateCause(check_id=check_id, positive=True, description="d",
                          supporting_ids=["b-01"], estimated_value=2340.0)


def _neg(check_id):
    return CandidateCause(check_id=check_id, positive=False, description="d")


BASE = {
    "investigation_session_id": "sess-1",
    "breaks": [{"break_id": "b-01", "book_ref": "APAC-CASH-01"}],
    "candidates": {"b-01": [_pos("C1")] + [_neg(c) for c in ("C2", "C3", "C4", "C5", "C6")]},
    "deltas": {"b-01": 2340.0},
    "pattern_groups": [PatternGroup(
        group_id="g1", pattern_code="P-204", label="FX timing lag",
        mode="auto", break_ids=["b-01"], historical_approval_rate=0.88)],
    "evidence_gaps": [],
    "hypothesis_attempts": 0,
}


async def test_single_candidate_takes_the_fast_path_and_skips_the_model():
    out = await rank(BASE, session=None)
    assert out["ranking"]["b-01"][0]["share_bps"] == 10000
    assert out["ranking"]["b-01"][0]["candidate_id"] == "C1"
    assert out["model_skipped"] is True


async def test_multiple_candidates_are_flagged_for_the_model():
    st = BASE | {"candidates": {"b-01": [_pos("C1"), _pos("C5")]
                                + [_neg(c) for c in ("C2", "C3", "C4", "C6")]}}
    out = await rank(st, session=None)
    assert out["model_skipped"] is False
    assert out["ranking"]["b-01"] == "needs_model"


async def test_draft_produces_the_four_part_narrative():
    st = BASE | await rank(BASE, session=None)
    out = await draft(st, session=None)
    d = out["draft"]
    assert isinstance(d, AnalysisDraft)
    assert "14" not in d.what_happened  # one break in this state, not fourteen
    assert "1 break" in d.what_happened
    assert "P-204" in d.why
    assert d.confidence_basis


async def test_validate_passes_a_grounded_draft():
    st = BASE | await rank(BASE, session=None)
    st |= await draft(st, session=None)
    out = await validate(st, session=None)
    assert out["validation_errors"] == []


async def test_validate_rejects_an_ungrounded_figure():
    """Every figure must trace to a delta. 9999.0 does not."""
    st = BASE | await rank(BASE, session=None)
    st |= await draft(st, session=None)
    st["draft"] = st["draft"].model_copy(
        update={"why": "The difference of $9,999.00 arose from a timing lag."}
    )
    out = await validate(st, session=None)
    assert any("ungrounded" in e for e in out["validation_errors"])


async def test_validate_reports_evidence_gaps():
    st = BASE | {"evidence_gaps": ["priors:b-01"]}
    st |= await rank(st, session=None)
    st |= await draft(st, session=None)
    out = await validate(st, session=None)
    assert any("evidence_gap" in e for e in out["validation_errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_nodes_rank_draft_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workflow.nodes.rank'`

- [ ] **Step 3: Write `apps/api/app/workflow/nodes/rank.py`**

```python
"""Rank candidate causes.

Fast path: a single positive candidate is assigned 10000 bps deterministically
and the model is skipped. About 60% of breaks take this path, which is why it
exists — it saves cost, latency and variance.

Multi-candidate ranking calls the reasoning client in Phase 3.
"""
from app.workflow.state import InvestigationState


async def rank(state: InvestigationState, *, session) -> dict:
    ranking: dict = {}
    model_skipped = True

    for brk in state["breaks"]:
        bid = brk["break_id"]
        positives = [c for c in state["candidates"][bid] if c.positive]
        if len(positives) == 1:
            ranking[bid] = [{
                "candidate_id": positives[0].check_id,
                "share_bps": 10000,
                "evidence_ids": positives[0].supporting_ids,
            }]
        else:
            ranking[bid] = "needs_model"
            model_skipped = False

    return {"ranking": ranking, "model_skipped": model_skipped}
```

- [ ] **Step 4: Write `apps/api/app/workflow/nodes/draft.py`**

```python
"""Produce the four-part narrative.

Phase 1 renders a deterministic template over grounded values, so every figure
traces to a delta by construction. Phase 3 replaces the template body with a
model call under a 400-token cap; the validator does not change.
"""
from app.contracts.models import AnalysisDraft
from app.workflow.state import InvestigationState


def _money(v: float) -> str:
    return f"${v:,.2f}"


async def draft(state: InvestigationState, *, session) -> dict:
    groups = state["pattern_groups"]
    n_breaks = len(state["breaks"])
    n_books = len({b["book_ref"] for b in state["breaks"]})
    brk_word = "break" if n_breaks == 1 else "breaks"
    book_word = "book" if n_books == 1 else "books"

    what = (f"{n_breaks} {brk_word} across {n_books} {book_word}, "
            f"grouped into {len(groups)} distinct root causes.")

    why_parts = []
    for g in groups:
        total = sum(state["deltas"].get(b, 0.0) for b in g.break_ids)
        why_parts.append(
            f"{len(g.break_ids)} attributed to {g.label} ({g.pattern_code}), "
            f"totalling {_money(total)}."
        )
    why = " ".join(why_parts)

    auto = [g for g in groups if g.mode == "auto"]
    todo = (f"Approve the {auto[0].pattern_code} group in one action. "
            if auto else "")
    todo += "Review the remaining groups individually before approving."

    gaps = state.get("evidence_gaps", [])
    risk = (f"{len(gaps)} evidence gap(s) on this run: {', '.join(gaps)}. "
            "Verify affected figures manually." if gaps
            else "No evidence gaps on this run.")

    rated = [g for g in groups if g.historical_approval_rate is not None]
    basis = " ".join(
        f"{g.pattern_code} has a {g.historical_approval_rate:.0%} historical approval rate."
        for g in rated
    ) or "No prior resolutions available for these patterns."

    return {"draft": AnalysisDraft(
        what_happened=what, why=why, what_to_do=todo,
        risk=risk, confidence_basis=basis,
    )}
```

- [ ] **Step 5: Write `apps/api/app/workflow/nodes/validate.py`**

```python
"""Hard assertions before a human ever sees the draft.

Every figure in the narrative must trace back to a computed delta. This is the
numeric-grounding validator, and its pass rate is what the analytics tab
reports — it measures grounding, not model confidence.
"""
import re

from app.workflow.state import MAX_HYPOTHESIS_ATTEMPTS, InvestigationState

MONEY = re.compile(r"\$([\d,]+\.\d{2})")


def _grounded_values(state: InvestigationState) -> set[str]:
    values = set()
    for v in state["deltas"].values():
        values.add(f"{v:,.2f}")
    for g in state["pattern_groups"]:
        total = sum(state["deltas"].get(b, 0.0) for b in g.break_ids)
        values.add(f"{total:,.2f}")
    return values


async def validate(state: InvestigationState, *, session) -> dict:
    errors: list[str] = []
    d = state.get("draft")
    if d is None:
        return {"validation_errors": ["no draft produced"]}

    grounded = _grounded_values(state)
    text = " ".join([d.what_happened, d.why, d.what_to_do, d.risk])
    for found in MONEY.findall(text):
        if found not in grounded:
            errors.append(f"ungrounded figure: ${found}")

    for g in state["pattern_groups"]:
        if not g.break_ids:
            errors.append(f"empty pattern group: {g.pattern_code}")

    for gap in state.get("evidence_gaps", []):
        errors.append(f"evidence_gap: {gap}")

    if state.get("hypothesis_attempts", 0) >= MAX_HYPOTHESIS_ATTEMPTS:
        errors.append("RETRY_EXHAUSTED")

    return {"validation_errors": errors}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_nodes_rank_draft_validate.py -v`
Expected: PASS, 6 tests

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/workflow/nodes/rank.py apps/api/app/workflow/nodes/draft.py apps/api/app/workflow/nodes/validate.py apps/api/tests/test_nodes_rank_draft_validate.py
git commit -m "feat: rank fast path, templated draft and the grounding validator"
```

---

### Task 9: Graph wiring, the review interrupt, and checkpoint/resume

**Files:**
- Create: `apps/api/app/workflow/graph.py`, `apps/api/app/workflow/nodes/record.py`
- Test: `apps/api/tests/test_checkpoint_resume.py`

**Interfaces:**
- Consumes: every node (Tasks 6–8)
- Produces:
  - `build_graph(checkpointer)` returning a compiled LangGraph with `interrupt_before=["review"]`
  - `async def run_investigation(state, *, thread_id, session)` 
  - `async def resume_investigation(thread_id, decisions, *, session)`

**This task is the phase's proof.** If checkpoint and resume do not survive a process restart, Phase 1 has not delivered.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_checkpoint_resume.py`:

```python
import json
from datetime import date
from pathlib import Path

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.contracts.models import Caller
from app.db.base import DATABASE_URL, get_session
from app.workflow.graph import build_graph, resume_investigation, run_investigation
from fixtures.loader import load_all

FIXTURE = Path(__file__).parents[1] / "fixtures" / "data" / "breaks_small.json"
FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")
DSN = DATABASE_URL.replace("+asyncpg", "")

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}


def _initial_state():
    rows = json.loads(FIXTURE.read_text())
    return {
        "investigation_session_id": "sess-resume", "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH", "business_date": date(2026, 8, 3),
        "run_id": "run-1100", "caller": FO,
        "breaks": [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in rows],
        "book_resolutions": {}, "evidence_gaps": [],
        "hypothesis_attempts": 0, "review_cycles": 0,
    }


async def test_run_pauses_at_the_review_interrupt():
    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            state = await run_investigation(
                _initial_state(), thread_id="sess-resume", session=s, checkpointer=cp
            )
        assert state["draft"] is not None
        assert len(state["pattern_groups"]) == 4
        assert state.get("outcome") is None, "must not have completed"


async def test_state_survives_a_fresh_process_and_resumes_to_completion():
    """The whole point of Phase 1: a second, independent checkpointer
    connection picks the thread up where it paused."""
    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            await run_investigation(
                _initial_state(), thread_id="sess-resume-2", session=s, checkpointer=cp
            )

    # New connection, as a restarted worker would have.
    async with get_session() as s2:
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp2:
            snapshot = await build_graph(cp2).aget_state(
                {"configurable": {"thread_id": "sess-resume-2"}}
            )
            assert snapshot.next == ("review",), "thread is not parked at review"
            assert len(snapshot.values["pattern_groups"]) == 4

            final = await resume_investigation(
                "sess-resume-2",
                decisions=[{"group_id": g.group_id, "action": "approve"}
                           for g in snapshot.values["pattern_groups"]],
                session=s2, checkpointer=cp2,
            )
            assert final["outcome"] == "recorded"


async def test_an_unresolvable_book_escalates_without_reaching_review():
    async with get_session() as s:
        await load_all(s)
        st = _initial_state() | {
            "investigation_session_id": "sess-esc",
            "breaks": [{"break_id": "b-x", "book_ref": "NOPE-01",
                        "fo_value": 1.0, "bo_value": 0.0, "cause": "C1"}],
        }
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            state = await run_investigation(
                st, thread_id="sess-esc", session=s, checkpointer=cp
            )
        assert state["outcome"] == "escalated"
        assert state["escalation_reason"] == "UNRESOLVED_BOOK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_checkpoint_resume.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.workflow.graph'`

- [ ] **Step 3: Write `apps/api/app/workflow/nodes/record.py`**

```python
"""Transactional write of the outcome.

Today's decision becomes tomorrow's prior: each approved break is stamped with
its pattern code and outcome so similar_breaks can find it.
"""
import uuid

from sqlalchemy import select

from app.db.models_session import AnalysisVersion, PatternGroupRow
from app.db.models_graph import BreakEvent
from app.workflow.state import InvestigationState


async def record(state: InvestigationState, *, session) -> dict:
    sid = state["investigation_session_id"]
    approved = {d["group_id"] for d in state.get("decisions", [])
                if d["action"] == "approve"}

    for g in state["pattern_groups"]:
        session.add(PatternGroupRow(
            group_id=g.group_id, investigation_session_id=sid,
            pattern_code=g.pattern_code, label=g.label, mode=g.mode,
            break_ids=g.break_ids,
            historical_approval_rate=g.historical_approval_rate,
        ))
        outcome = "approved" if g.group_id in approved else "rejected"
        for bid in g.break_ids:
            brk = await session.scalar(
                select(BreakEvent).where(BreakEvent.break_id == bid)
            )
            if brk is not None:
                brk.pattern_code = g.pattern_code
                brk.outcome = outcome
                brk.narrative = g.label

    d = state["draft"]
    session.add(AnalysisVersion(
        analysis_version_id=str(uuid.uuid4()),
        investigation_session_id=sid, supersedes=None,
        summary=d.model_dump(), confidence_tier="high",
        prompt_version="phase1-template-v1",
        skill_version="phase1", model_identifier="none",
    ))
    await session.commit()
    return {"outcome": "recorded"}
```

- [ ] **Step 4: Write `apps/api/app/workflow/graph.py`**

```python
"""Graph wiring.

The sequence is fixed: resolve -> gather -> group -> rank -> draft ->
validate -> review (interrupt) -> record. The model never chooses what
happens next. Escalation short-circuits from resolve or gather.

thread_id = investigation_session_id, at rec/book/run grain, so the review
interrupt fires once per session and the controller approves per pattern group.
"""
from functools import partial

from langgraph.graph import END, StateGraph

from app.workflow.nodes.draft import draft
from app.workflow.nodes.escalate import escalate
from app.workflow.nodes.gather import gather
from app.workflow.nodes.group import group
from app.workflow.nodes.rank import rank
from app.workflow.nodes.record import record
from app.workflow.nodes.resolve import resolve
from app.workflow.nodes.validate import validate
from app.workflow.state import InvestigationState


async def _review(state: InvestigationState) -> dict:
    """Pure pass-through. The pause happens at interrupt_before."""
    return {"review_cycles": state.get("review_cycles", 0) + 1}


def _after(node_state: InvestigationState) -> str:
    return "escalate" if node_state.get("outcome") == "escalated" else "continue"


def build_graph(checkpointer, *, session=None):
    bind = lambda fn: partial(fn, session=session) if session is not None else fn

    g = StateGraph(InvestigationState)
    g.add_node("resolve", bind(resolve))
    g.add_node("gather", bind(gather))
    g.add_node("group", bind(group))
    g.add_node("rank", bind(rank))
    g.add_node("draft", bind(draft))
    g.add_node("validate", bind(validate))
    g.add_node("review", _review)
    g.add_node("record", bind(record))
    g.add_node("escalate", escalate)

    g.set_entry_point("resolve")
    g.add_conditional_edges("resolve", _after,
                            {"continue": "gather", "escalate": "escalate"})
    g.add_conditional_edges("gather", _after,
                            {"continue": "group", "escalate": "escalate"})
    g.add_edge("group", "rank")
    g.add_edge("rank", "draft")
    g.add_edge("draft", "validate")
    g.add_edge("validate", "review")
    g.add_edge("review", "record")
    g.add_edge("record", END)
    g.add_edge("escalate", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=["review"])


async def run_investigation(state, *, thread_id, session, checkpointer):
    app = build_graph(checkpointer, session=session)
    config = {"configurable": {"thread_id": thread_id}}
    await app.ainvoke(state, config)
    return (await app.aget_state(config)).values


async def resume_investigation(thread_id, decisions, *, session, checkpointer):
    app = build_graph(checkpointer, session=session)
    config = {"configurable": {"thread_id": thread_id}}
    await app.aupdate_state(config, {"decisions": decisions})
    await app.ainvoke(None, config)
    return (await app.aget_state(config)).values
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_checkpoint_resume.py -v`
Expected: PASS, 3 tests. The second test is the phase's proof.

- [ ] **Step 6: Run the whole backend suite**

Run: `cd apps/api && python -m pytest -v`
Expected: PASS, 34 tests

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/workflow/graph.py apps/api/app/workflow/nodes/record.py apps/api/tests/test_checkpoint_resume.py
git commit -m "feat: langgraph wiring with review interrupt and postgres checkpointing"
```

---

### Task 10: API routes and the WebSocket handler

**Files:**
- Create: `apps/api/api/main.py`, `apps/api/api/config.py`, `apps/api/api/auth.py`, `apps/api/api/routes/runs.py`, `apps/api/api/routes/sessions.py`, `apps/api/api/routes/breaks.py`, `apps/api/api/websocket/handler.py`
- Test: `apps/api/tests/test_api.py`

**Interfaces:**
- Consumes: `run_investigation` (Task 9), ORM models (Task 2)
- Produces: HTTP surface consumed by the console in Tasks 11–13:
  - `GET /api/runs` → `{regions: [{region, recs: [{rec_id, name, scheduled, status, books_open, books_total}]}], stats: {...}}`
  - `GET /api/sessions/{session_id}` → `{session, draft, pattern_groups, pipeline_stage}`
  - `POST /api/sessions/{session_id}/investigate` → 202
  - `GET /api/breaks?session_id=` → `{breaks: [...], total: int}`
  - `WS /api/ws/runs` → `run.progress` events

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_api.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from app.db.base import get_session
from fixtures.loader import load_all


@pytest.fixture
async def client():
    async with get_session() as s:
        await load_all(s)
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_runs_returns_three_regions(client):
    r = await client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert {x["region"] for x in body["regions"]} == {"APAC", "EMEA", "AMER"}


async def test_runs_carries_the_stat_chips_the_header_shows(client):
    body = (await client.get("/api/runs")).json()
    for key in ("recs", "cleared", "awaiting", "blocked",
                "adj_pending", "auto_posted", "books_open", "books_not_open"):
        assert key in body["stats"], f"missing stat: {key}"


async def test_investigate_then_read_the_session(client):
    r = await client.post("/api/sessions/sess-api/investigate")
    assert r.status_code == 202
    body = (await client.get("/api/sessions/sess-api")).json()
    assert len(body["pattern_groups"]) == 4
    assert body["draft"]["what_happened"]


async def test_unknown_session_is_404_not_an_empty_shell(client):
    r = await client.get("/api/sessions/does-not-exist")
    assert r.status_code == 404


async def test_breaks_are_paged(client):
    await client.post("/api/sessions/sess-api/investigate")
    body = (await client.get("/api/breaks?session_id=sess-api&limit=5")).json()
    assert len(body["breaks"]) == 5
    assert body["total"] == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Write `apps/api/api/auth.py`**

```python
"""Development caller stub.

Constructs the same Caller object real auth would. Swapping to BAM plus the
entitlement service touches this function and nothing else.
"""
from app.contracts.models import Caller

DEV_CALLER = Caller(
    staff_id="praveen",
    roles=["FO", "PC"],
    entity_scope=["LE-APAC-01"],
    region="APAC",
)


def current_caller() -> Caller:
    return DEV_CALLER
```

- [ ] **Step 4: Write `apps/api/api/routes/runs.py`**

The run schedule the header and timeline render. Static in Phase 1; driven by real sessions in Phase 2.

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["runs"])

REGIONS = [
    {"region": "APAC", "recs": [
        {"rec_id": "R-1050", "name": "CATS vs MOTIF — Rates", "scheduled": "11:00",
         "status": "cleared", "books_open": 22, "books_total": 22, "adj_pending": 0},
        {"rec_id": "R-1055", "name": "Rec Factory — Cash Recon", "scheduled": "11:00",
         "status": "awaiting", "books_open": 9, "books_total": 11, "adj_pending": 14},
        {"rec_id": "R-1060", "name": "CATS vs MOTIF — FX", "scheduled": "19:00",
         "status": "scheduled", "books_open": 0, "books_total": 15, "adj_pending": 0},
    ]},
    {"region": "EMEA", "recs": [
        {"rec_id": "R-2010", "name": "CATS vs MOTIF — Credit", "scheduled": "15:00",
         "status": "in_progress", "books_open": 11, "books_total": 19, "adj_pending": 0},
        {"rec_id": "R-2015", "name": "Rec Factory — Collateral", "scheduled": "15:00",
         "status": "blocked", "books_open": 1, "books_total": 7, "adj_pending": 0},
    ]},
    {"region": "AMER", "recs": [
        {"rec_id": "R-3010", "name": "CATS vs MOTIF — Equities", "scheduled": "17:00",
         "status": "scheduled", "books_open": 0, "books_total": 41, "adj_pending": 0},
        {"rec_id": "R-3015", "name": "Rec Factory — Cash Recon", "scheduled": "17:00",
         "status": "cleared", "books_open": 13, "books_total": 13, "adj_pending": 0},
    ]},
]

RUN_WINDOWS = ["11:00", "15:00", "17:00", "19:00"]


def _stats() -> dict:
    recs = [r for reg in REGIONS for r in reg["recs"]]
    return {
        "recs": len(recs),
        "cleared": sum(1 for r in recs if r["status"] == "cleared"),
        "awaiting": sum(1 for r in recs if r["status"] == "awaiting"),
        "blocked": sum(1 for r in recs if r["status"] == "blocked"),
        "adj_pending": sum(r["adj_pending"] for r in recs),
        "auto_posted": 32,
        "books_open": sum(r["books_open"] for r in recs),
        "books_not_open": sum(r["books_total"] - r["books_open"] for r in recs),
        "unlocked": 53,
        "unlocked_total": 160,
        "now": "17:40",
        "next_run": "19:00",
        "timezone": "IST",
        "business_date": "2026-08-03",
    }


@router.get("/runs")
async def get_runs() -> dict:
    return {"regions": REGIONS, "run_windows": RUN_WINDOWS, "stats": _stats()}
```

- [ ] **Step 5: Write `apps/api/api/routes/sessions.py`**

```python
import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from api.auth import current_caller
from app.db.base import DATABASE_URL, get_session
from app.workflow.graph import build_graph, run_investigation
from fixtures.loader import load_all

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

FIXTURE = Path(__file__).parents[3] / "fixtures" / "data" / "breaks_small.json"
DSN = DATABASE_URL.replace("+asyncpg", "")

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}

PIPELINE_STAGES = [
    {"key": "mbr", "label": "MBR / Rec Factory", "sub": "CATS ↔ MOTIF breaks"},
    {"key": "analysis", "label": "FOBO Agent Analysis", "sub": "Manual / Auto adjustments"},
    {"key": "signoff", "label": "Human Sign-off", "sub": "Reviewed & approved"},
    {"key": "post", "label": "Post to MOTIF", "sub": "via FAS"},
    {"key": "notify", "label": "Notify P&L Agent", "sub": "Book Unlocked"},
]


def _initial_state(session_id: str) -> dict:
    rows = json.loads(FIXTURE.read_text())
    return {
        "investigation_session_id": session_id, "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH", "business_date": date(2026, 8, 3),
        "run_id": "run-1100", "caller": current_caller(),
        "breaks": [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in rows],
        "book_resolutions": {}, "evidence_gaps": [],
        "hypothesis_attempts": 0, "review_cycles": 0,
    }


@router.post("/{session_id}/investigate", status_code=202)
async def investigate(session_id: str) -> Response:
    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            await run_investigation(
                _initial_state(session_id), thread_id=session_id,
                session=s, checkpointer=cp,
            )
    return Response(status_code=202)


@router.get("/{session_id}")
async def get_session_detail(session_id: str) -> dict:
    async with get_session() as s:
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            snapshot = await build_graph(cp, session=s).aget_state(
                {"configurable": {"thread_id": session_id}}
            )
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="no such investigation session")

    v = snapshot.values
    parked_at_review = snapshot.next == ("review",)
    return {
        "session": {
            "investigation_session_id": session_id,
            "reconciliation_id": v["reconciliation_id"],
            "master_book": v["master_book"],
            "business_date": str(v["business_date"]),
            "run_id": v["run_id"],
            "status": "awaiting_signoff" if parked_at_review else (v.get("outcome") or "analysing"),
        },
        "draft": v["draft"].model_dump() if v.get("draft") else None,
        "pattern_groups": [g.model_dump() for g in v.get("pattern_groups", [])],
        "pipeline_stage": "signoff" if parked_at_review else "analysis",
        "pipeline_stages": PIPELINE_STAGES,
        "evidence_gaps": v.get("evidence_gaps", []),
        "validation_errors": v.get("validation_errors", []),
    }
```

- [ ] **Step 6: Write `apps/api/api/routes/breaks.py`**

```python
from fastapi import APIRouter
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.base import DATABASE_URL, get_session
from app.workflow.graph import build_graph

router = APIRouter(prefix="/api", tags=["breaks"])
DSN = DATABASE_URL.replace("+asyncpg", "")


@router.get("/breaks")
async def list_breaks(session_id: str, limit: int = 50, offset: int = 0) -> dict:
    async with get_session() as s:
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            snapshot = await build_graph(cp, session=s).aget_state(
                {"configurable": {"thread_id": session_id}}
            )
    breaks = snapshot.values.get("breaks", []) if snapshot.values else []
    deltas = snapshot.values.get("deltas", {}) if snapshot.values else {}
    page = breaks[offset:offset + limit]
    return {
        "breaks": [{
            "break_id": b["break_id"], "book_ref": b["book_ref"],
            "line_code": b.get("line_code", "CASH"),
            "delta": deltas.get(b["break_id"]),
        } for b in page],
        "total": len(breaks),
        "truncated": offset + limit < len(breaks),
    }
```

- [ ] **Step 7: Write `apps/api/api/websocket/handler.py`**

```python
"""run.progress emitter.

Phase 1 replays node progress for one session. Phase 2 streams it live from
the running graph. The event shape is the contract and does not change.
"""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.contracts.models import RunProgress

router = APIRouter()

NODE_SEQUENCE = ["resolve", "gather", "group", "rank", "draft", "validate", "review"]


@router.websocket("/api/ws/runs")
async def runs_socket(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            session_id = msg.get("session_id")
            if not session_id:
                continue
            for i, node in enumerate(NODE_SEQUENCE, start=1):
                await ws.send_json(RunProgress(
                    session_id=session_id, node=node,
                    breaks_processed=int(14 * i / len(NODE_SEQUENCE)),
                    breaks_total=14,
                ).model_dump(mode="json"))
                await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        return
```

- [ ] **Step 8: Write `apps/api/api/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import breaks, runs, sessions
from api.websocket import handler


def create_app() -> FastAPI:
    app = FastAPI(title="FOBO Investigation API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3100"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(runs.router)
    app.include_router(sessions.router)
    app.include_router(breaks.router)
    app.include_router(handler.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd apps/api && python -m pytest tests/test_api.py -v`
Expected: PASS, 5 tests

- [ ] **Step 10: Start the API and check it by hand**

Run: `cd apps/api && uvicorn api.main:app --port 8100 --reload`
Then: `curl -s localhost:8100/api/runs | head -20`
Expected: JSON with three regions

- [ ] **Step 11: Commit**

```bash
git add apps/api/api apps/api/tests/test_api.py
git commit -m "feat: runs, sessions and breaks routes with a run.progress socket"
```

---

### Task 11: Console scaffold, design tokens and the top bar

**Files:**
- Create: `apps/console/package.json`, `apps/console/next.config.mjs`, `apps/console/vitest.config.js`, `apps/console/src/app/layout.js`, `apps/console/src/app/globals.css`, `apps/console/src/styles/tokens.css`, `apps/console/src/lib/apiClient.js`, `apps/console/src/components/fobo/shell/TopBar.jsx`
- Test: `apps/console/src/components/fobo/shell/TopBar.test.jsx`

**Interfaces:**
- Consumes: `GET /api/runs` (Task 10)
- Produces: `<TopBar stats={...} activeTab tabs onTabChange />`, `apiClient.get(path)`

- [ ] **Step 1: Scaffold the app**

Run:
```bash
mkdir -p apps/console && cd apps/console
npm init -y
npm i next@latest react@latest react-dom@latest zustand
npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom tailwindcss@next @tailwindcss/postcss
```

- [ ] **Step 2: Write `apps/console/package.json` scripts**

Replace the `scripts` block with:

```json
{
  "scripts": {
    "dev": "next dev -p 3100",
    "build": "next build",
    "start": "next start -p 3100",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 3: Write `apps/console/vitest.config.js`**

```js
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.js'],
  },
});
```

And `apps/console/vitest.setup.js`:

```js
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 4: Generate `tokens.css` from the design source**

Run:
```bash
cp docs/design/mock-tokens.css apps/console/src/styles/tokens.css
```

This file is generated. Never hand-edit it — edit `docs/design/mock-tokens.css` and re-copy.

- [ ] **Step 5: Write `apps/console/src/app/globals.css`**

```css
@import "tailwindcss";
@import "../styles/tokens.css";

body {
  background: var(--bg-page);
  color: var(--text-primary);
  font-family: Inter, system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.glass-card {
  background: var(--bg-card);
  backdrop-filter: var(--card-blur);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card);
  box-shadow: var(--card-shadow);
}

.pill {
  border-radius: var(--radius-pill);
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 500;
}
```

- [ ] **Step 6: Write the failing test**

Create `apps/console/src/components/fobo/shell/TopBar.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import TopBar from './TopBar';

const STATS = {
  business_date: '2026-08-03',
  timezone: 'IST',
  next_run: '19:00',
};

describe('TopBar', () => {
  it('shows the product name and the horizontal-service subtitle', () => {
    render(<TopBar stats={STATS} activeTab="pipeline" onTabChange={() => {}} />);
    expect(screen.getByText('FOBO Control Tower')).toBeInTheDocument();
    expect(screen.getByText(/horizontal FOBO service across 280 P&Ls/)).toBeInTheDocument();
  });

  it('renders the business date and next run from stats, not hardcoded', () => {
    render(<TopBar stats={{ ...STATS, next_run: '21:00' }} activeTab="pipeline" onTabChange={() => {}} />);
    expect(screen.getByText(/21:00/)).toBeInTheDocument();
  });

  it('marks the active tab with aria-current', () => {
    render(<TopBar stats={STATS} activeTab="analytics" onTabChange={() => {}} />);
    expect(screen.getByRole('button', { name: /Agent Analytics/ }))
      .toHaveAttribute('aria-current', 'page');
  });

  it('calls onTabChange when a tab is clicked', async () => {
    const onTabChange = vi.fn();
    const { default: userEvent } = await import('@testing-library/user-event');
    render(<TopBar stats={STATS} activeTab="pipeline" onTabChange={onTabChange} />);
    await userEvent.click(screen.getByRole('button', { name: /Agent Analytics/ }));
    expect(onTabChange).toHaveBeenCalledWith('analytics');
  });
});
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd apps/console && npm i -D @testing-library/user-event && npm test`
Expected: FAIL — cannot resolve `./TopBar`

- [ ] **Step 8: Write `apps/console/src/components/fobo/shell/TopBar.jsx`**

```jsx
'use client';

const TABS = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'analytics', label: 'Agent Analytics' },
];

function formatDate(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}

export default function TopBar({ stats, activeTab, onTabChange }) {
  return (
    <header
      className="flex items-center gap-6 px-6 py-3"
      style={{ background: 'var(--header-grad)', color: 'var(--text-on-brand)' }}
    >
      <div className="min-w-0">
        <h1
          className="text-lg font-bold leading-tight truncate"
          style={{ fontFamily: 'Manrope, system-ui, sans-serif' }}
        >
          FOBO Control Tower
        </h1>
        <p className="text-xs truncate" style={{ color: 'var(--text-on-brand2)' }}>
          Agent One · horizontal FOBO service across 280 P&amp;Ls
        </p>
      </div>

      <span
        className="pill flex items-center gap-2 shrink-0"
        style={{ background: 'rgba(255,255,255,0.10)' }}
      >
        {formatDate(stats.business_date)}
        <span style={{ color: 'var(--text-on-brand2)' }}>{stats.timezone}</span>
      </span>

      <nav className="flex items-center gap-1">
        {TABS.map((tab) => {
          const active = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              type="button"
              aria-current={active ? 'page' : undefined}
              onClick={() => onTabChange(tab.key)}
              className="pill"
              style={{
                background: active ? 'rgba(255,255,255,0.16)' : 'transparent',
                color: 'var(--text-on-brand)',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <span
        className="pill ml-auto shrink-0"
        style={{ background: 'rgba(255,255,255,0.10)' }}
      >
        Next run <strong>{stats.next_run} {stats.timezone}</strong>
      </span>
    </header>
  );
}
```

- [ ] **Step 9: Write `apps/console/src/lib/apiClient.js`**

```js
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8100';

export async function get(path) {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`POST ${path} failed: ${res.status}`);
  }
  return res.status === 202 ? null : res.json();
}
```

- [ ] **Step 10: Write `apps/console/src/app/layout.js`**

```jsx
import './globals.css';

export const metadata = {
  title: 'FOBO Control Tower — Agent One',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `cd apps/console && npm test`
Expected: PASS, 4 tests

- [ ] **Step 12: Commit**

```bash
git add apps/console
git commit -m "feat: console scaffold with barclays tokens and the control tower top bar"
```

---

### Task 12: Run schedule card and region rail

**Files:**
- Create: `apps/console/src/components/fobo/schedule/StatChipRow.jsx`, `apps/console/src/components/fobo/schedule/RunScheduleCard.jsx`, `apps/console/src/components/fobo/regions/RegionRail.jsx`, `apps/console/src/store/foboRunStore.js`
- Test: `apps/console/src/components/fobo/schedule/StatChipRow.test.jsx`, `apps/console/src/components/fobo/regions/RegionRail.test.jsx`

**Interfaces:**
- Consumes: `GET /api/runs` shape (Task 10)
- Produces: `<StatChipRow stats />`, `<RunScheduleCard stats regions runWindows />`, `<RegionRail regions selectedRecId onSelectRec />`, `useFoboRunStore`

- [ ] **Step 1: Write the failing tests**

Create `apps/console/src/components/fobo/schedule/StatChipRow.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatChipRow from './StatChipRow';

const STATS = {
  recs: 7, cleared: 2, awaiting: 1, blocked: 1, adj_pending: 14,
  auto_posted: 32, books_open: 56, books_not_open: 72,
  unlocked: 53, unlocked_total: 160,
};

describe('StatChipRow', () => {
  it('renders every chip from the mock', () => {
    render(<StatChipRow stats={STATS} />);
    for (const label of ['recs', 'cleared', 'awaiting', 'blocked', 'adj. pending',
      'auto-posted', 'books open', 'not open']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('shows unlocked as a fraction', () => {
    render(<StatChipRow stats={STATS} />);
    expect(screen.getByText('53/160')).toBeInTheDocument();
  });

  it('reads values from props rather than hardcoding', () => {
    render(<StatChipRow stats={{ ...STATS, adj_pending: 99 }} />);
    expect(screen.getByText('99')).toBeInTheDocument();
  });
});
```

Create `apps/console/src/components/fobo/regions/RegionRail.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import RegionRail from './RegionRail';

const REGIONS = [
  { region: 'APAC', recs: [
    { rec_id: 'R-1050', name: 'CATS vs MOTIF — Rates', scheduled: '11:00',
      status: 'cleared', books_open: 22, books_total: 22, adj_pending: 0 },
    { rec_id: 'R-1055', name: 'Rec Factory — Cash Recon', scheduled: '11:00',
      status: 'awaiting', books_open: 9, books_total: 11, adj_pending: 14 },
  ] },
  { region: 'EMEA', recs: [
    { rec_id: 'R-2015', name: 'Rec Factory — Collateral', scheduled: '15:00',
      status: 'blocked', books_open: 1, books_total: 7, adj_pending: 0 },
  ] },
];

describe('RegionRail', () => {
  it('groups recs under their region', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={() => {}} />);
    expect(screen.getByText('APAC')).toBeInTheDocument();
    expect(screen.getByText('EMEA')).toBeInTheDocument();
  });

  it('shows the open/total book count per rec', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={() => {}} />);
    expect(screen.getByText('11:00 IST · 9/11 open')).toBeInTheDocument();
  });

  it('badges a rec that has pending adjustments', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={() => {}} />);
    expect(screen.getByLabelText('14 adjustments pending')).toBeInTheDocument();
  });

  it('marks the selected rec', () => {
    render(<RegionRail regions={REGIONS} selectedRecId="R-1055" onSelectRec={() => {}} />);
    expect(screen.getByRole('button', { name: /Rec Factory — Cash Recon/ }))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onSelectRec with the rec id', async () => {
    const onSelectRec = vi.fn();
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={onSelectRec} />);
    await userEvent.click(screen.getByRole('button', { name: /Collateral/ }));
    expect(onSelectRec).toHaveBeenCalledWith('R-2015');
  });

  it('filters recs by the search box', async () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={() => {}} />);
    await userEvent.type(screen.getByPlaceholderText('Search recs...'), 'Collateral');
    expect(screen.queryByText('CATS vs MOTIF — Rates')).not.toBeInTheDocument();
    expect(screen.getByText('Rec Factory — Collateral')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/console && npm test`
Expected: FAIL — cannot resolve `./StatChipRow` and `./RegionRail`

- [ ] **Step 3: Write `apps/console/src/components/fobo/schedule/StatChipRow.jsx`**

```jsx
const CHIPS = [
  { key: 'recs', label: 'recs', color: 'var(--text-primary)' },
  { key: 'cleared', label: 'cleared', color: 'var(--clr-green)' },
  { key: 'awaiting', label: 'awaiting', color: 'var(--clr-amber)' },
  { key: 'blocked', label: 'blocked', color: 'var(--clr-red)' },
  { key: 'adj_pending', label: 'adj. pending', color: 'var(--clr-purple)' },
  { key: 'auto_posted', label: 'auto-posted', color: 'var(--clr-green)' },
  { key: 'books_open', label: 'books open', color: 'var(--clr-blue)' },
  { key: 'books_not_open', label: 'not open', color: 'var(--text-muted)' },
];

export default function StatChipRow({ stats }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      {CHIPS.map(({ key, label, color }) => (
        <span key={key} className="flex items-baseline gap-1">
          <strong style={{ color }}>{stats[key]}</strong>
          <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        </span>
      ))}
      <span className="flex items-baseline gap-1">
        <strong style={{ color: 'var(--clr-blue)' }}>
          {stats.unlocked}/{stats.unlocked_total}
        </strong>
        <span style={{ color: 'var(--text-muted)' }}>unlocked</span>
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Write `apps/console/src/components/fobo/schedule/RunScheduleCard.jsx`**

```jsx
import StatChipRow from './StatChipRow';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

const STATUS_DOT = {
  cleared: 'var(--bar-cleared)',
  awaiting: 'var(--bar-awaiting)',
  blocked: 'var(--bar-blocked)',
  in_progress: 'var(--bar-analysing)',
  scheduled: 'var(--bar-notopen)',
};

export default function RunScheduleCard({ stats, regions, runWindows }) {
  return (
    <section className="glass-card p-4">
      <div className="flex items-baseline gap-3 mb-2">
        <h2
          className="text-xs font-bold tracking-wide"
          style={{ color: 'var(--text-primary)', fontFamily: 'Manrope, sans-serif' }}
        >
          RUN SCHEDULE — TODAY
        </h2>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          now {stats.now} {stats.timezone} · next {stats.next_run}
        </span>
      </div>

      <StatChipRow stats={stats} />

      <div
        className="mt-4 grid gap-x-2 gap-y-2 items-center"
        style={{ gridTemplateColumns: `56px repeat(${runWindows.length}, 1fr)` }}
      >
        <div />
        {runWindows.map((w) => (
          <div key={w} className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {w}
          </div>
        ))}

        {regions.map(({ region, recs }) => (
          <RegionRow
            key={region}
            region={region}
            recs={recs}
            runWindows={runWindows}
          />
        ))}
      </div>
    </section>
  );
}

function RegionRow({ region, recs, runWindows }) {
  return (
    <>
      <span
        className="pill text-center font-semibold"
        style={REGION_STYLE[region]}
      >
        {region}
      </span>
      {runWindows.map((window) => {
        const inWindow = recs.filter((r) => r.scheduled === window);
        return (
          <div key={window} className="flex flex-wrap gap-1">
            {inWindow.map((rec) => (
              <span
                key={rec.rec_id}
                className="pill flex items-center gap-1.5 whitespace-nowrap"
                style={{
                  background: 'var(--bg-muted)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: STATUS_DOT[rec.status],
                  }}
                />
                {rec.name.split('—').pop().trim()}
                <span style={{ color: 'var(--text-muted)' }}>
                  {rec.books_open}/{rec.books_total}
                </span>
              </span>
            ))}
          </div>
        );
      })}
    </>
  );
}
```

- [ ] **Step 5: Write `apps/console/src/components/fobo/regions/RegionRail.jsx`**

```jsx
'use client';

import { useState } from 'react';

const REGION_STYLE = {
  APAC: { background: 'var(--apac-bg)', color: 'var(--apac-text)' },
  EMEA: { background: 'var(--emea-bg)', color: 'var(--emea-text)' },
  AMER: { background: 'var(--amer-bg)', color: 'var(--amer-text)' },
};

const STATUS_BAR = {
  cleared: 'var(--bar-cleared)',
  awaiting: 'var(--bar-awaiting)',
  blocked: 'var(--bar-blocked)',
  in_progress: 'var(--bar-analysing)',
  scheduled: 'var(--bar-notopen)',
};

export default function RegionRail({ regions, selectedRecId, onSelectRec }) {
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();

  const filtered = regions
    .map((r) => ({
      ...r,
      recs: needle
        ? r.recs.filter((rec) => rec.name.toLowerCase().includes(needle))
        : r.recs,
    }))
    .filter((r) => r.recs.length > 0);

  return (
    <aside className="glass-card p-3 flex flex-col gap-3">
      <h2
        className="text-xs font-bold tracking-wide"
        style={{ color: 'var(--text-primary)', fontFamily: 'Manrope, sans-serif' }}
      >
        REGIONS &amp; RECS
      </h2>

      <input
        type="search"
        value={query}
        placeholder="Search recs..."
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-lg px-3 py-1.5 text-sm"
        style={{
          background: 'var(--bg-muted)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
      />

      {filtered.map(({ region, recs }) => (
        <div key={region} className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="pill font-semibold" style={REGION_STYLE[region]}>
              {region}
            </span>
          </div>
          {recs.map((rec) => (
            <RecRow
              key={rec.rec_id}
              rec={rec}
              selected={rec.rec_id === selectedRecId}
              onSelect={() => onSelectRec(rec.rec_id)}
            />
          ))}
        </div>
      ))}
    </aside>
  );
}

function RecRow({ rec, selected, onSelect }) {
  const pct = rec.books_total === 0
    ? 0
    : Math.round((rec.books_open / rec.books_total) * 100);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className="w-full text-left rounded-lg px-2 py-1.5 transition"
      style={{
        background: selected ? 'var(--bg-active)' : 'transparent',
        border: `1px solid ${selected ? 'var(--clr-blue)' : 'transparent'}`,
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>
          {rec.name}
        </span>
        {rec.adj_pending > 0 && (
          <span
            className="pill shrink-0"
            aria-label={`${rec.adj_pending} adjustments pending`}
            style={{ background: 'var(--clr-purple-bg)', color: 'var(--clr-purple)' }}
          >
            {rec.adj_pending}
          </span>
        )}
      </div>
      <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
        {rec.scheduled} IST · {rec.books_open}/{rec.books_total} open
      </div>
      <div
        className="mt-1 h-1 rounded-full overflow-hidden"
        style={{ background: 'var(--bar-notopen)' }}
      >
        <div
          style={{
            width: `${pct}%`, height: '100%',
            background: STATUS_BAR[rec.status],
          }}
        />
      </div>
    </button>
  );
}
```

- [ ] **Step 6: Write `apps/console/src/store/foboRunStore.js`**

```js
import { create } from 'zustand';

import { get } from '@/lib/apiClient';

export const useFoboRunStore = create((set) => ({
  regions: [],
  runWindows: [],
  stats: null,
  selectedRecId: null,
  loading: false,
  error: null,

  selectRec: (recId) => set({ selectedRecId: recId }),

  loadRuns: async () => {
    set({ loading: true, error: null });
    try {
      const data = await get('/api/runs');
      set({
        regions: data.regions,
        runWindows: data.run_windows,
        stats: data.stats,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
```

Add the `@` alias in `apps/console/jsconfig.json`:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

And in `vitest.config.js`, add to the config object:

```js
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/console && npm test`
Expected: PASS, 13 tests

- [ ] **Step 8: Commit**

```bash
git add apps/console
git commit -m "feat: run schedule card, stat chips and searchable region rail"
```

---

### Task 13: Pipeline rail and the wired Control Tower page

**Files:**
- Create: `apps/console/src/components/fobo/pipeline/PipelineRail.jsx`, `apps/console/src/lib/WebSocketClient.js`, `apps/console/src/hooks/useRunStream.js`, `apps/console/src/store/foboSessionStore.js`, `apps/console/src/app/fobo/page.js`
- Test: `apps/console/src/components/fobo/pipeline/PipelineRail.test.jsx`

**Interfaces:**
- Consumes: `GET /api/sessions/{id}` and `WS /api/ws/runs` (Task 10), `useFoboRunStore` (Task 12)
- Produces: `<PipelineRail stages currentStage counts />`, `useFoboSessionStore`, the `/fobo` page

- [ ] **Step 1: Write the failing test**

Create `apps/console/src/components/fobo/pipeline/PipelineRail.test.jsx`:

```jsx
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PipelineRail from './PipelineRail';

const STAGES = [
  { key: 'mbr', label: 'MBR / Rec Factory', sub: 'CATS ↔ MOTIF breaks' },
  { key: 'analysis', label: 'FOBO Agent Analysis', sub: 'Manual / Auto adjustments' },
  { key: 'signoff', label: 'Human Sign-off', sub: 'Reviewed & approved' },
  { key: 'post', label: 'Post to MOTIF', sub: 'via FAS' },
  { key: 'notify', label: 'Notify P&L Agent', sub: 'Book Unlocked' },
];

const COUNTS = { auto_posted: 3, awaiting_signoff: 9, not_open: 2 };

describe('PipelineRail', () => {
  it('renders every stage with its subtitle', () => {
    render(<PipelineRail stages={STAGES} currentStage="signoff" counts={COUNTS} />);
    expect(screen.getByText('MBR / Rec Factory')).toBeInTheDocument();
    expect(screen.getByText('via FAS')).toBeInTheDocument();
  });

  it('marks stages before the current one as complete', () => {
    render(<PipelineRail stages={STAGES} currentStage="signoff" counts={COUNTS} />);
    expect(screen.getByLabelText('MBR / Rec Factory: complete')).toBeInTheDocument();
    expect(screen.getByLabelText('FOBO Agent Analysis: complete')).toBeInTheDocument();
  });

  it('marks the current stage as active', () => {
    render(<PipelineRail stages={STAGES} currentStage="signoff" counts={COUNTS} />);
    expect(screen.getByLabelText('Human Sign-off: active')).toBeInTheDocument();
  });

  it('marks later stages as pending', () => {
    render(<PipelineRail stages={STAGES} currentStage="signoff" counts={COUNTS} />);
    expect(screen.getByLabelText('Post to MOTIF: pending')).toBeInTheDocument();
  });

  it('shows the stacked progress legend', () => {
    render(<PipelineRail stages={STAGES} currentStage="signoff" counts={COUNTS} />);
    const legend = screen.getByRole('list', { name: 'Book status' });
    expect(within(legend).getByText(/3/)).toBeInTheDocument();
    expect(within(legend).getByText(/auto-posted/)).toBeInTheDocument();
    expect(within(legend).getByText(/9/)).toBeInTheDocument();
    expect(within(legend).getByText(/awaiting sign-off/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/console && npm test`
Expected: FAIL — cannot resolve `./PipelineRail`

- [ ] **Step 3: Write `apps/console/src/components/fobo/pipeline/PipelineRail.jsx`**

```jsx
const SEGMENTS = [
  { key: 'auto_posted', label: 'auto-posted', color: 'var(--bar-auto)' },
  { key: 'awaiting_signoff', label: 'awaiting sign-off', color: 'var(--bar-awaiting)' },
  { key: 'not_open', label: 'not open yet', color: 'var(--bar-notopen)' },
];

function stageState(stages, currentStage, index) {
  const currentIndex = stages.findIndex((s) => s.key === currentStage);
  if (index < currentIndex) return 'complete';
  if (index === currentIndex) return 'active';
  return 'pending';
}

const STATE_STYLE = {
  complete: { background: 'var(--clr-green-bg)', color: 'var(--clr-green)',
              border: '1px solid var(--clr-green)' },
  active: { background: 'var(--clr-blue-bg)', color: 'var(--clr-blue)',
            border: '2px solid var(--clr-blue)' },
  pending: { background: 'var(--bg-muted)', color: 'var(--text-muted)',
             border: '1px dashed var(--border)' },
};

export default function PipelineRail({ stages, currentStage, counts }) {
  const total = SEGMENTS.reduce((sum, s) => sum + (counts[s.key] ?? 0), 0);

  return (
    <section className="flex flex-col gap-3">
      <ol className="flex items-start gap-1">
        {stages.map((stage, i) => {
          const state = stageState(stages, currentStage, i);
          return (
            <li key={stage.key} className="flex-1 flex flex-col items-center gap-1.5">
              <div className="flex items-center w-full">
                <span
                  className="h-px flex-1"
                  style={{ background: i === 0 ? 'transparent' : 'var(--border)' }}
                />
                <span
                  aria-label={`${stage.label}: ${state}`}
                  className="flex items-center justify-center rounded-full shrink-0"
                  style={{ width: 34, height: 34, ...STATE_STYLE[state] }}
                >
                  {state === 'complete' ? '✓' : i + 1}
                </span>
                <span
                  className="h-px flex-1"
                  style={{
                    background: i === stages.length - 1 ? 'transparent' : 'var(--border)',
                  }}
                />
              </div>
              <span
                className="text-xs font-medium text-center leading-tight"
                style={{ color: 'var(--text-primary)' }}
              >
                {stage.label}
              </span>
              <span
                className="text-[11px] text-center leading-tight"
                style={{ color: 'var(--text-muted)' }}
              >
                {stage.sub}
              </span>
            </li>
          );
        })}
      </ol>

      <div
        className="flex h-2 rounded-full overflow-hidden"
        style={{ background: 'var(--bar-notopen)' }}
      >
        {SEGMENTS.map((seg) => {
          const value = counts[seg.key] ?? 0;
          if (total === 0 || value === 0) return null;
          return (
            <div
              key={seg.key}
              style={{ width: `${(value / total) * 100}%`, background: seg.color }}
            />
          );
        })}
      </div>

      <ul aria-label="Book status" className="flex flex-wrap gap-4 text-xs">
        {SEGMENTS.map((seg) => (
          <li key={seg.key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              style={{
                width: 7, height: 7, borderRadius: '50%', background: seg.color,
              }}
            />
            <strong style={{ color: 'var(--text-primary)' }}>
              {counts[seg.key] ?? 0}
            </strong>
            <span style={{ color: 'var(--text-muted)' }}>{seg.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Write `apps/console/src/lib/WebSocketClient.js`**

```js
/**
 * Auto-reconnecting socket keyed by investigation_session_id.
 * All state lives in Postgres, so a reconnect landing on a different
 * worker loses nothing.
 */
const BASE = process.env.NEXT_PUBLIC_WS_BASE ?? 'ws://localhost:8100';

export class WebSocketClient {
  constructor(path, { onEvent, onError } = {}) {
    this.url = `${BASE}${path}`;
    this.onEvent = onEvent ?? (() => {});
    this.onError = onError ?? (() => {});
    this.socket = null;
    this.closed = false;
    this.retryMs = 500;
    this.pending = [];
  }

  connect() {
    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.retryMs = 500;
      for (const msg of this.pending.splice(0)) {
        this.socket.send(JSON.stringify(msg));
      }
    };

    this.socket.onmessage = (event) => {
      try {
        this.onEvent(JSON.parse(event.data));
      } catch (err) {
        this.onError(err);
      }
    };

    this.socket.onclose = () => {
      if (this.closed) return;
      setTimeout(() => this.connect(), this.retryMs);
      this.retryMs = Math.min(this.retryMs * 2, 10000);
    };

    this.socket.onerror = (err) => this.onError(err);
    return this;
  }

  send(message) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      this.pending.push(message);
    }
  }

  close() {
    this.closed = true;
    this.socket?.close();
  }
}
```

- [ ] **Step 5: Write `apps/console/src/store/foboSessionStore.js`**

```js
import { create } from 'zustand';

import { get, post } from '@/lib/apiClient';

export const useFoboSessionStore = create((set) => ({
  session: null,
  draft: null,
  patternGroups: [],
  pipelineStages: [],
  pipelineStage: null,
  evidenceGaps: [],
  progress: null,
  loading: false,
  error: null,

  setProgress: (progress) => set({ progress }),

  investigate: async (sessionId) => {
    set({ loading: true, error: null });
    try {
      await post(`/api/sessions/${sessionId}/investigate`);
      const data = await get(`/api/sessions/${sessionId}`);
      set({
        session: data.session,
        draft: data.draft,
        patternGroups: data.pattern_groups,
        pipelineStages: data.pipeline_stages,
        pipelineStage: data.pipeline_stage,
        evidenceGaps: data.evidence_gaps,
        loading: false,
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },
}));
```

- [ ] **Step 6: Write `apps/console/src/hooks/useRunStream.js`**

```js
'use client';

import { useEffect } from 'react';

import { WebSocketClient } from '@/lib/WebSocketClient';
import { useFoboSessionStore } from '@/store/foboSessionStore';

export function useRunStream(sessionId) {
  const setProgress = useFoboSessionStore((s) => s.setProgress);

  useEffect(() => {
    if (!sessionId) return undefined;

    const client = new WebSocketClient('/api/ws/runs', {
      onEvent: (event) => {
        if (event.type === 'run.progress') setProgress(event);
      },
    }).connect();

    client.send({ session_id: sessionId });
    return () => client.close();
  }, [sessionId, setProgress]);
}
```

- [ ] **Step 7: Write `apps/console/src/app/fobo/page.js`**

```jsx
'use client';

import { useEffect, useState } from 'react';

import PipelineRail from '@/components/fobo/pipeline/PipelineRail';
import RegionRail from '@/components/fobo/regions/RegionRail';
import RunScheduleCard from '@/components/fobo/schedule/RunScheduleCard';
import TopBar from '@/components/fobo/shell/TopBar';
import { useRunStream } from '@/hooks/useRunStream';
import { useFoboRunStore } from '@/store/foboRunStore';
import { useFoboSessionStore } from '@/store/foboSessionStore';

const SESSION_ID = 'sess-r1055';

export default function FoboControlTower() {
  const [tab, setTab] = useState('pipeline');
  const { regions, runWindows, stats, selectedRecId, selectRec, loadRuns } =
    useFoboRunStore();
  const { draft, patternGroups, pipelineStages, pipelineStage, progress, investigate } =
    useFoboSessionStore();

  useEffect(() => { loadRuns(); }, [loadRuns]);
  useEffect(() => { investigate(SESSION_ID); }, [investigate]);
  useRunStream(SESSION_ID);

  if (!stats) {
    return <p className="p-6" style={{ color: 'var(--text-muted)' }}>Loading…</p>;
  }

  const counts = {
    auto_posted: 3,
    awaiting_signoff: patternGroups.reduce((n, g) => n + g.break_ids.length, 0),
    not_open: 2,
  };

  return (
    <div className="min-h-screen flex flex-col">
      <TopBar stats={stats} activeTab={tab} onTabChange={setTab} />

      <main className="flex-1 p-4 flex flex-col gap-4">
        <RunScheduleCard stats={stats} regions={regions} runWindows={runWindows} />

        <div className="grid gap-4" style={{ gridTemplateColumns: '260px 1fr' }}>
          <RegionRail
            regions={regions}
            selectedRecId={selectedRecId}
            onSelectRec={selectRec}
          />

          <section className="glass-card p-4 flex flex-col gap-4">
            {progress && (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                {progress.node} · {progress.breaks_processed}/{progress.breaks_total} breaks
              </p>
            )}

            {pipelineStages.length > 0 && (
              <PipelineRail
                stages={pipelineStages}
                currentStage={pipelineStage}
                counts={counts}
              />
            )}

            {draft && (
              <div className="flex flex-col gap-2">
                <h3
                  className="text-sm font-bold"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                >
                  Agent Analysis
                </h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {draft.what_happened}
                </p>
              </div>
            )}
          </section>
        </div>
      </main>

      <footer
        className="px-6 py-3 text-center text-xs"
        style={{ color: 'var(--text-muted)' }}
      >
        Draft UI — illustrative data. Every posting step still requires human
        sign-off before MOTIF posting.
      </footer>
    </div>
  );
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd apps/console && npm test`
Expected: PASS, 18 tests

- [ ] **Step 9: End-to-end smoke check**

Run in three terminals:
```bash
docker compose up -d postgres
cd apps/api && uvicorn api.main:app --port 8100
cd apps/console && npm run dev
```
Open `http://localhost:3100/fobo`. Expected: the navy header, the run schedule with stat chips and the region timeline, the searchable region rail, the pipeline rail with Human Sign-off active, and the analysis line reading "14 breaks across 11 books, grouped into 4 distinct root causes."

- [ ] **Step 10: Commit**

```bash
git add apps/console
git commit -m "feat: pipeline rail and control tower page wired to the live workflow"
```

---

## Phase 1 exit criteria

| Criterion | Verified by |
|---|---|
| The workflow runs end to end on fixtures | `test_checkpoint_resume.py::test_run_pauses_at_the_review_interrupt` |
| State survives a fresh process and resumes | `test_checkpoint_resume.py::test_state_survives_a_fresh_process_and_resumes_to_completion` |
| 14 breaks collapse to 4 decisions | `test_node_group.py::test_fourteen_breaks_collapse_to_four_groups` |
| Entitlement is enforced in the query | `test_repository.py::test_a_caller_outside_the_entity_scope_cannot_resolve` |
| `as_of` returns the historical hierarchy | `test_repository.py::test_as_of_returns_the_hierarchy_in_force_on_that_date` |
| Cause checks are deterministic | `test_recon.py::test_is_deterministic` |
| Ungrounded figures are caught | `test_nodes_rank_draft_validate.py::test_validate_rejects_an_ungrounded_figure` |
| The console renders the mock's shell | `npm test` (18 tests) plus the Step 9 smoke check |

**Not in Phase 1** (and deliberately so): the analysis panel's WHY/WHAT TO DO/RISK rendering, the grounding MCP call list, the drafted-adjustments column with approve-all, the analytics tab, any MCP tool group, the chat drawer, and any LLM call. Those are Phases 2–4.

---

## Self-review notes

- **Spec coverage.** Phase 1 scope in spec §21 is "contracts package, Postgres schema, fixture loader, LangGraph happy path through the review interrupt, console shell with run schedule and pipeline rail". Tasks 1–13 cover all five. Spec §3.1 (session grain) is implemented in Task 9's `thread_id`; §3.2 (the `group` node) in Task 7; §8.4 (entitlement) in Task 4; §14 (caller stub) in Task 10.
- **Deferred with intent.** `book_context` is built in Task 4 and used by the `as_of` test, but no Phase 1 node calls it; `gather` calls `lineage` instead. It is consumed in Phase 2 by the analysis panel.
- **Type consistency.** `PatternGroup.break_ids`, `historical_approval_rate`, `pattern_code` and `mode` are used identically in Tasks 1, 7, 9, 10 and 13. `AnalysisDraft`'s four fields plus `confidence_basis` match between Tasks 1, 8, 10 and 13.
- **Known gap to close in Phase 2.** `api/routes/sessions.py` calls `load_all` on every investigate, which resets fixtures. That is correct for a fixture-backed Phase 1 and must be removed when real sessions are persisted.
