# Workflow Configuration Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versioned, four-eyes workflow configuration stored in Postgres, edited from a new Workflow tab in the Helix console, with YAML import/export, and every LangGraph run pinned to the version it started with.

**Architecture:** A `workflow_version` table becomes the authority for which workflow runs; the checked-in YAML seeds version 1. A store module (`app/workflow/versions.py`) enforces the draft → second-approver rules. `run_investigation` records the active version on the run and binds its config in a `ContextVar`, so `settings()` inside every LangGraph step returns the run's own version. A new `/api/workflow` router serves the catalogue, versions, diff, rebase, validation and YAML. The console gets a Workflow tab: a graph view with who-decides tags, a draft editor with live validation, and a versions panel with approve/reject.

**Tech Stack:** FastAPI 0.141, Pydantic 2.13, SQLAlchemy 2 async + asyncpg, Alembic, LangGraph with the Postgres checkpointer, PyYAML; Next 16, React 19 (JavaScript, not TypeScript), Tailwind v4, lucide-react, vitest + Testing Library; Playwright for the end-to-end test.

**Spec:** `docs/superpowers/specs/2026-09-24-workflow-config-screen-design.md`

## Global Constraints

- Backend tests: `cd apps/api && .venv/bin/python -m pytest -q` (Postgres at `localhost:5433`, database `fobo_test`, created by `tests/conftest.py`). Baseline: 260 passing.
- Console tests: `cd apps/console && npx vitest run`. Baseline: 55 passing.
- Commit format: `<type>: <description>` (feat, fix, refactor, docs, test, chore). Every commit ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Version statuses, verbatim: `draft`, `active`, `superseded`, `rejected`.
- `decided_by` values, verbatim: `code`, `playbook+reasoner`, `code+model`, `template`, `human`.
- Dev callers: `praveen` (roles `FO`, `PC`) and `asha` (role `PC`). Header `X-Dev-Caller`, honoured only when `FOBO_ENV=dev`.
- Approve requires header `Idempotency-Key`. Notes: 1–500 characters. YAML uploads: at most 64 KB. Editor validation debounce: 400 ms.
- JavaScript helpers never mutate their inputs; return new objects.
- Files stay under ~300 lines; functions under ~50 lines.
- Console colours come only from existing CSS variables (`--clr-green`, `--clr-green-bg`, `--clr-amber`, `--clr-amber-bg`, `--clr-red`, `--clr-red-bg`, `--clr-blue`, `--clr-blue-bg`, `--clr-purple`, `--clr-purple-bg`, `--bg-muted`, `--bg-card-solid`, `--bg-hover`, `--border`, `--text-primary`, `--text-secondary`, `--text-muted`, `--card-shadow`, `--card-shadow-md`, `--bg-header-deep`, `--text-on-brand2`).
- Run the full backend suite before every backend commit and the full console suite before every console commit. Nothing that passed before may fail after.

## Review Focus

1. **Two approvals racing** (double click, two browser tabs) for two drafts based on the same active version: exactly one becomes active and the other gets a 409; never two active versions. Test in Task 5.
2. **JSONB loses key order**: a config read back from Postgres must still export as YAML in the order `version, name, steps, pause_before, settings`, and diffs must not report reordering that did not happen. Test in Task 7.
3. **A numeric setting sent as an empty string** from the form (the user cleared the field): validation answers `ok: false` with the field named, never a 500; saving it is a 422. Test in Task 8.
4. **Runs from before this feature** (an `investigation_session` row with no `workflow_version`): trace and decisions keep working and read the run as v1. Test in Task 6.
5. **Browser storage blocked** (private window): the dev caller switch still works for the page's lifetime and nothing throws. Test in Task 9.

---

## File Structure

**Backend (`apps/api`)**

| File | Responsibility |
|---|---|
| `api/auth.py` (modify) | Caller `ContextVar`, dev callers, dev-caller middleware |
| `api/main.py` (modify) | Install middleware, `VersionError` handler, workflow router, configurable CORS origins |
| `api/routes/workflow.py` (create) | `/api/workflow` endpoints |
| `api/routes/helix.py` (modify) | Board lists `devCallers` in dev; chat reads the reasoner from the active version |
| `api/cases.py`, `api/routes/decisions.py`, `api/routes/sessions.py` (modify) | Read checkpoints through `graph_for_session` |
| `app/db/models_workflow.py` (create) | `WorkflowVersion` model |
| `app/db/models_session.py` (modify) | `InvestigationSession.workflow_version` column |
| `migrations/versions/f3b8d1c6a4e7_workflow_version.py` (create) | Table, index, column |
| `migrations/env.py` (modify) | Register the new model module |
| `app/workflow/config.py` (modify) | `dump_config`, `errors_of`, `settings_schema`, `use_workflow`, bound `settings()`, field descriptions |
| `app/workflow/registry.py` (modify) | `decided_by`, `catalogue()`, `workflow_version` initial input |
| `app/workflow/cli.py` (modify) | Use `errors_of` |
| `app/workflow/diff.py` (create) | Pure `diff` and `rebase` |
| `app/workflow/versions.py` (create) | Version store and rules |
| `app/workflow/yaml_io.py` (create) | YAML export and parsing |
| `app/workflow/graph.py` (modify) | Pin on run; `pinned_for_session`, `graph_for_session` |
| `app/workflow/session.py` (modify) | Write the version onto the session row |
| `app/workflow/state.py` (modify) | `workflow_version` in state |
| `app/queries/trace.py` (modify) | Steps and version from the run's pinned workflow |
| `config/workflow/fobo-investigation.yaml` (modify, repo root) | Header comment: the file seeds v1 |
| `scripts/reset_e2e_db.py` (create) | Fresh `fobo_e2e` database |
| `tests/…` (create) | One test file per task, named in each task |

**Console (`apps/console`)**

| File | Responsibility |
|---|---|
| `src/lib/apiClient.js` (modify) | Dev caller header, `ApiError` with structured errors, `getText` |
| `src/components/helix/data/workflowApi.js` (create) | Every call the Workflow tab makes |
| `src/components/helix/workflow/workflowModel.js` (create) | Pure helpers: chips, edits, diff lines |
| `src/components/helix/workflow/StepCard.jsx` (create) | One step card |
| `src/components/helix/workflow/WorkflowGraph.jsx` (create) | The graph, view or edit mode |
| `src/components/helix/workflow/StepPanel.jsx` (create) | Step side panel |
| `src/components/helix/workflow/SettingsForm.jsx` (create) | Settings inputs from the schema |
| `src/components/helix/workflow/DraftEditor.jsx` (create) | Edit state, validation, save |
| `src/components/helix/workflow/ErrorList.jsx` (create) | An `ApiError`'s message and list |
| `src/components/helix/workflow/WorkflowDialog.jsx` (create) | Confirm dialog |
| `src/components/helix/workflow/VersionList.jsx` (create) | History with status chips |
| `src/components/helix/workflow/VersionDetail.jsx` (create) | Diff, approve, reject, redraft |
| `src/components/helix/workflow/YamlUpload.jsx` (create) | Upload drawer |
| `src/components/helix/workflow/ActiveStrip.jsx` (create) | Active version strip |
| `src/components/helix/workflow/WorkflowView.jsx` (create) | Tab container |
| `src/components/helix/workflow/DevCallerSwitch.jsx` (create) | Header switcher |
| `src/components/helix/workflow/__fixtures__/workflow.json` (create) | Generated `/api/workflow` response |
| `src/components/helix/HelixApp.jsx` (modify) | Workflow tab, dev caller switch |
| `src/components/fobo/execution/WorkflowTrace.jsx` (modify) | "workflow vN" instead of the file name |
| `next.config.mjs` (modify) | `NEXT_DIST_DIR` for the e2e server |
| `playwright.config.js`, `e2e/reset-db.mjs`, `e2e/workflow.spec.js` (create) | End-to-end test |

---

### Task 1: Dev caller switching

**Files:**
- Modify: `apps/api/api/auth.py`
- Modify: `apps/api/api/main.py`
- Modify: `apps/api/api/routes/helix.py` (the `board` handler)
- Test: `apps/api/tests/test_dev_caller.py`

**Interfaces:**
- Produces: `api.auth.current_caller() -> Caller` (unchanged signature, now context-aware); `api.auth.DEV_CALLERS: dict[str, Caller]`; `api.auth.dev_mode() -> bool`; `api.auth.dev_callers() -> list[dict] | None` (each `{"id", "roles"}`, `None` outside dev); `api.auth.dev_caller_middleware(request, call_next)`; `api.auth.DEV_CALLER_HEADER = "X-Dev-Caller"`. Board response gains `devCallers` (dev only).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_dev_caller.py`:

```python
"""A second dev caller, so a change drafted by one person can be approved by another."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.auth import DEV_CALLERS, current_caller, dev_caller_middleware
from api.main import create_app


def _probe_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(dev_caller_middleware)

    @app.get("/who")
    async def who() -> dict:
        c = current_caller()
        return {"id": c.staff_id, "roles": c.roles}

    return app


async def _who(headers=None):
    async with AsyncClient(transport=ASGITransport(app=_probe_app()),
                           base_url="http://test") as c:
        return await c.get("/who", headers=headers or {})


async def test_without_the_header_the_caller_is_the_stub(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    assert (await _who()).json()["id"] == "praveen"


async def test_in_dev_the_header_selects_another_caller(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    assert (await _who({"X-Dev-Caller": "asha"})).json() == {"id": "asha", "roles": ["PC"]}


async def test_outside_dev_the_header_is_ignored(monkeypatch):
    monkeypatch.delenv("FOBO_ENV", raising=False)
    assert (await _who({"X-Dev-Caller": "asha"})).json()["id"] == "praveen"


async def test_an_unknown_dev_caller_is_refused_with_the_valid_names(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    r = await _who({"X-Dev-Caller": "mallory"})
    assert r.status_code == 400
    assert "praveen" in r.json()["detail"] and "asha" in r.json()["detail"]


async def test_the_binding_does_not_leak_into_the_next_request(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    await _who({"X-Dev-Caller": "asha"})
    assert (await _who()).json()["id"] == "praveen"


def test_both_dev_callers_are_product_control():
    assert all("PC" in c.roles for c in DEV_CALLERS.values())


async def test_the_api_app_installs_the_switch(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test") as c:
        r = await c.get("/health", headers={"X-Dev-Caller": "mallory"})
    assert r.status_code == 400


async def test_the_board_names_the_caller_and_lists_dev_callers_only_in_dev(monkeypatch):
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        monkeypatch.setenv("FOBO_ENV", "dev")
        board = (await c.get("/api/helix/board", headers={"X-Dev-Caller": "asha"})).json()
        assert board["caller"]["id"] == "asha"
        assert [d["id"] for d in board["devCallers"]] == ["praveen", "asha"]
        monkeypatch.delenv("FOBO_ENV")
        assert "devCallers" not in (await c.get("/api/helix/board")).json()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_dev_caller.py -q`
Expected: FAIL — `ImportError: cannot import name 'DEV_CALLERS'`.

- [ ] **Step 3: Implement the caller context**

Replace `apps/api/api/auth.py` with:

```python
"""Development caller stub.

Constructs the same Caller object real auth would. Swapping to BAM plus the
entitlement service touches this module and nothing else — which is the
whole reason the Caller is built in one place.

In development (FOBO_ENV=dev) a request may act as another dev caller by
sending X-Dev-Caller. That exists so a workflow change drafted by one person
can be approved by a second; outside dev the header is ignored.
"""

import os
from contextvars import ContextVar

from fastapi.responses import JSONResponse

from app.contracts.models import Caller

DEV_CALLER = Caller(
    staff_id="praveen",
    roles=["FO", "PC"],
    entity_scope=["LE-APAC-01"],
    region="APAC",
)

DEV_CALLERS: dict[str, Caller] = {
    "praveen": DEV_CALLER,
    "asha": Caller(
        staff_id="asha",
        roles=["PC"],
        entity_scope=["LE-APAC-01"],
        region="APAC",
    ),
}

DEV_CALLER_HEADER = "X-Dev-Caller"

_caller: ContextVar[Caller | None] = ContextVar("fobo_caller", default=None)


def dev_mode() -> bool:
    return os.getenv("FOBO_ENV", "").strip().lower() == "dev"


def current_caller() -> Caller:
    return _caller.get() or DEV_CALLER


def dev_callers() -> list[dict] | None:
    """The callers the console may switch between; None outside dev."""
    if not dev_mode():
        return None
    return [{"id": c.staff_id, "roles": list(c.roles)} for c in DEV_CALLERS.values()]


async def dev_caller_middleware(request, call_next):
    """Act as another dev caller for this request, when FOBO_ENV=dev."""
    name = request.headers.get(DEV_CALLER_HEADER)
    if not name or not dev_mode():
        return await call_next(request)
    caller = DEV_CALLERS.get(name.strip().lower())
    if caller is None:
        return JSONResponse(
            status_code=400,
            content={"detail": f"unknown dev caller '{name}' — use one of: "
                               f"{', '.join(DEV_CALLERS)}"},
        )
    token = _caller.set(caller)
    try:
        return await call_next(request)
    finally:
        _caller.reset(token)
```

- [ ] **Step 4: Install the middleware**

In `apps/api/api/main.py`, add `from api.auth import dev_caller_middleware` to the imports, and in `create_app()` register it **before** `app.add_middleware(CORSMiddleware, ...)` (the last middleware added is the outermost, so CORS then wraps it and a refused caller still gets CORS headers):

```python
    app = FastAPI(title="FOBO Investigation API", version="0.1.0")
    # Registered before CORS so CORS wraps it: a refused dev caller still
    # gets the CORS headers the browser needs to read the 400.
    app.middleware("http")(dev_caller_middleware)
    app.add_middleware(
        CORSMiddleware,
```

- [ ] **Step 5: List dev callers on the board**

In `apps/api/api/routes/helix.py`, import `dev_callers` alongside `current_caller` (`from api.auth import current_caller, dev_callers`) and change the `board` handler's return into:

```python
        body = {
            "cob": str(business_date),
            "caller": _caller(),
            "recs": [views[rec.rec_id] for rec, _ in rows],
            "activity": await _feed(s, business_date, rows, views),
            # Derived with its assumption stated, e.g. "36 decisions avoided at
            # 12 min each"; the console shows the value and the basis together.
            "hoursSaved": await hours_saved(s, business_date),
        }
        callers = dev_callers()
        if callers:
            body["devCallers"] = callers
        return body
```

- [ ] **Step 6: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_dev_caller.py -q` → PASS. Then the full suite: `.venv/bin/python -m pytest -q` → all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/api/auth.py apps/api/api/main.py apps/api/api/routes/helix.py apps/api/tests/test_dev_caller.py
git commit -m "feat: dev caller switch, so a second person can approve

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The `workflow_version` table

**Files:**
- Create: `apps/api/app/db/models_workflow.py`
- Modify: `apps/api/app/db/models_session.py` (imports; `InvestigationSession`)
- Create: `apps/api/migrations/versions/f3b8d1c6a4e7_workflow_version.py`
- Modify: `apps/api/migrations/env.py:24`
- Modify: `apps/api/tests/conftest.py` (imports, `TABLES`)
- Test: `apps/api/tests/test_workflow_version_model.py`

**Interfaces:**
- Produces: `app.db.models_workflow.WorkflowVersion` with columns `number:int (PK)`, `config:dict (JSONB)`, `status:str`, `based_on:int|None`, `note:str`, `drafted_by:str`, `drafted_at:datetime`, `decided_by:str|None`, `decided_at:datetime|None`, `reject_reason:str|None`, `decision_key:str|None (unique)`. `InvestigationSession.workflow_version: int | None` (FK → `workflow_version.number`).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_version_model.py`:

```python
"""The database itself guarantees one active workflow version."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import get_session
from app.db.models_workflow import WorkflowVersion


def _row(number: int, status: str, **kw) -> WorkflowVersion:
    return WorkflowVersion(
        number=number, config={"steps": []}, status=status, note="n",
        drafted_by="praveen", drafted_at=datetime.now(timezone.utc), **kw,
    )


async def test_a_version_round_trips():
    async with get_session() as s:
        s.add(_row(1, "active"))
        await s.commit()
    async with get_session() as s:
        got = await s.get(WorkflowVersion, 1)
        assert got.status == "active" and got.config == {"steps": []}


async def test_the_database_refuses_a_second_active_version():
    async with get_session() as s:
        s.add(_row(1, "active"))
        await s.commit()
        s.add(_row(2, "active"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_any_number_of_drafts_may_coexist():
    async with get_session() as s:
        s.add_all([_row(1, "active"), _row(2, "draft", based_on=1), _row(3, "draft", based_on=1)])
        await s.commit()


async def test_an_unknown_status_is_refused():
    async with get_session() as s:
        s.add(_row(1, "live"))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_a_decision_key_is_used_once():
    async with get_session() as s:
        s.add_all([_row(1, "superseded", decision_key="k"), _row(2, "active", decision_key="k")])
        with pytest.raises(IntegrityError):
            await s.commit()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_version_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.models_workflow'`.

- [ ] **Step 3: Create the model**

Create `apps/api/app/db/models_workflow.py`:

```python
"""Workflow versions: which LangGraph workflow runs, and who decided it.

The database is the authority. The checked-in YAML seeds version 1; after
that a version changes only through a draft that a second Product Control
user approves (app/workflow/versions.py). Nothing is ever deleted.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STATUSES = ("draft", "active", "superseded", "rejected")


class WorkflowVersion(Base):
    __tablename__ = "workflow_version"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'rejected')",
            name="ck_workflow_version_status",
        ),
        # Exactly one active version is a database guarantee, not a convention.
        Index(
            "uq_workflow_version_one_active", "status", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    config: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    based_on: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_version.number"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text)
    drafted_by: Mapped[str] = mapped_column(String(64))
    drafted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
```

- [ ] **Step 4: Add the run's version to the session row**

In `apps/api/app/db/models_session.py`: add `Integer` to the `from sqlalchemy import (...)` list, add `from app.db import models_workflow  # noqa: F401 — the workflow_version FK target` after `from app.db.base import Base`, and add this column to `InvestigationSession` after `status`:

```python
    # The workflow version the run started with. Null: the run predates
    # versioning and is read as version 1.
    workflow_version: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_version.number"), nullable=True
    )
```

- [ ] **Step 5: Register the tables for tests and migrations**

In `apps/api/tests/conftest.py` change the models import to
`from app.db import models_graph, models_ops, models_session, models_workflow  # noqa: E402,F401`
and add `"workflow_version",` to `TABLES` directly after `"investigation_session",`.

In `apps/api/migrations/env.py:24` change the import to
`from app.db import models_graph, models_ops, models_session, models_workflow  # noqa: F401  register tables`.

- [ ] **Step 6: Write the migration**

Create `apps/api/migrations/versions/f3b8d1c6a4e7_workflow_version.py`:

```python
"""workflow versions: the database decides which workflow runs

Revision ID: f3b8d1c6a4e7
Revises: e5a7c3d9f1b2
Create Date: 2026-09-24 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f3b8d1c6a4e7"
down_revision: Union[str, Sequence[str], None] = "e5a7c3d9f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_version",
        sa.Column("number", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("based_on", sa.Integer(), sa.ForeignKey("workflow_version.number"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("drafted_by", sa.String(64), nullable=False),
        sa.Column("drafted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("decision_key", sa.String(128), nullable=True, unique=True),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'rejected')",
            name="ck_workflow_version_status",
        ),
    )
    op.create_index(
        "uq_workflow_version_one_active", "workflow_version", ["status"],
        unique=True, postgresql_where=sa.text("status = 'active'"),
    )
    op.add_column(
        "investigation_session",
        sa.Column("workflow_version", sa.Integer(),
                  sa.ForeignKey("workflow_version.number"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investigation_session", "workflow_version")
    op.drop_index("uq_workflow_version_one_active", table_name="workflow_version")
    op.drop_table("workflow_version")
```

- [ ] **Step 7: Run the tests, then migrate the dev database**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_version_model.py -q` → PASS.
Run the full suite → all pass.
Migrate the development database: `cd apps/api && .venv/bin/alembic upgrade head` → ends with `Running upgrade e5a7c3d9f1b2 -> f3b8d1c6a4e7`.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/db/models_workflow.py apps/api/app/db/models_session.py apps/api/migrations apps/api/tests/conftest.py apps/api/tests/test_workflow_version_model.py
git commit -m "feat: workflow_version table, one active version enforced by the database

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Step catalogue, settings schema, and one error formatter

**Files:**
- Modify: `apps/api/app/workflow/registry.py`
- Modify: `apps/api/app/workflow/config.py`
- Modify: `apps/api/app/workflow/cli.py`
- Test: `apps/api/tests/test_workflow_catalogue.py`

**Interfaces:**
- Produces:
  - `app.workflow.registry.Step.decided_by: str` (default `"code"`); `DECIDED_BY: tuple[str, ...]`; `catalogue() -> list[dict]` — each `{name, label, description, decided_by, removable, required_because, can_escalate, needs, produces, must_follow}` (lists sorted); `INITIAL_INPUTS` now includes `"workflow_version"`.
  - `app.workflow.config.dump_config(cfg: WorkflowConfig) -> dict` — JSON-safe, by alias (`validate`), field order preserved.
  - `app.workflow.config.errors_of(exc: Exception) -> list[str]` — one line per problem, no leading `- `.
  - `app.workflow.config.settings_schema() -> dict[str, dict[str, dict]]` — section (YAML name) → field → `{type, default, description, [min], [max], [exclusive_min], [options]}`; `type` ∈ `integer | number | string | string_list | enum`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_catalogue.py`:

```python
"""What the Workflow tab is told about each step and setting."""

import copy
import json

import pytest
import yaml
from pydantic import ValidationError

from app.workflow.config import (
    DEFAULT_PATH,
    WorkflowConfig,
    dump_config,
    errors_of,
    read_workflow,
    settings_schema,
)
from app.workflow.registry import DECIDED_BY, INITIAL_INPUTS, STEPS, catalogue


def _raw():
    return copy.deepcopy(yaml.safe_load(DEFAULT_PATH.read_text()))


def test_the_catalogue_describes_every_registered_step_in_registry_order():
    assert [s["name"] for s in catalogue()] == list(STEPS)


def test_each_step_says_who_decides_it():
    by = {s["name"]: s["decided_by"] for s in catalogue()}
    assert by == {
        "resolve": "code", "gather": "code", "group": "code",
        "reason": "playbook+reasoner", "rank": "code+model", "draft": "template",
        "validate": "code", "review": "human", "record": "code",
    }
    assert set(by.values()) <= set(DECIDED_BY)


def test_only_rank_is_removable():
    assert [s["name"] for s in catalogue() if s["removable"]] == ["rank"]


def test_every_locked_step_says_why():
    for s in catalogue():
        assert s["removable"] or s["required_because"]


def test_the_catalogue_is_plain_json():
    json.dumps(catalogue())


def test_the_run_supplies_its_workflow_version():
    assert "workflow_version" in INITIAL_INPUTS


def test_dump_config_uses_yaml_names_and_order():
    d = dump_config(read_workflow())
    assert list(d) == ["version", "name", "steps", "pause_before", "settings"]
    assert "validate" in d["settings"] and "validate_" not in d["settings"]
    assert WorkflowConfig.model_validate(d) == read_workflow()


def test_the_settings_schema_carries_the_validators_bounds():
    schema = settings_schema()
    depth = schema["gather"]["lineage_max_depth"]
    assert (depth["type"], depth["min"], depth["max"], depth["default"]) == ("integer", 1, 4, 4)
    timeout = schema["session_service"]["timeout_seconds"]
    assert timeout["type"] == "number" and timeout["exclusive_min"] == 0


def test_the_reasoner_is_offered_as_a_choice():
    r = settings_schema()["reason"]["reasoner"]
    assert r["type"] == "enum" and r["options"] == ["none", "session_service", "direct"]


def test_policy_params_are_a_string_list():
    assert settings_schema()["reason"]["verdict_policy_params"]["type"] == "string_list"


def test_the_schema_uses_yaml_section_names():
    assert list(settings_schema()) == ["gather", "reason", "validate", "review", "session_service"]


def test_every_setting_is_described():
    for fields in settings_schema().values():
        for meta in fields.values():
            assert meta["description"]


def test_errors_of_lists_every_ordering_problem_one_per_line():
    raw = _raw()
    raw["steps"].remove("reason")
    raw["steps"].remove("validate")
    with pytest.raises(ValidationError) as exc:
        WorkflowConfig.model_validate(raw)
    errs = errors_of(exc.value)
    assert any("'reason' cannot be removed" in e for e in errs)
    assert any("'validate' cannot be removed" in e for e in errs)
    assert not any(e.startswith("- ") for e in errs)


def test_errors_of_names_the_field_of_a_misspelt_setting():
    raw = _raw()
    raw["settings"]["gather"]["prior_lookback_days"] = 90
    with pytest.raises(ValidationError) as exc:
        WorkflowConfig.model_validate(raw)
    assert errors_of(exc.value) == [
        "settings.gather.prior_lookback_days: Extra inputs are not permitted"
    ]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_catalogue.py -q`
Expected: FAIL — `ImportError: cannot import name 'dump_config'`.

- [ ] **Step 3: Registry — `decided_by` and `catalogue()`**

In `apps/api/app/workflow/registry.py`:

1. Add a field to `Step`, after `must_follow`:

```python
    # Who or what decides the step's output; the Workflow tab tags each step
    # with it. One of DECIDED_BY.
    decided_by: str = "code"
```

2. Add `"workflow_version"` to `INITIAL_INPUTS`.
3. Pass `decided_by=` in the `STEPS` list: `reason` → `"playbook+reasoner"`, `rank` → `"code+model"`, `draft` → `"template"`, `review` → `"human"`. The others keep the default.
4. After `PAUSE_REQUIRED`, add:

```python
DECIDED_BY = ("code", "playbook+reasoner", "code+model", "template", "human")


def catalogue() -> list[dict]:
    """Every registered step as the Workflow tab shows it, in registry order."""
    return [
        {
            "name": s.name,
            "label": s.label,
            "description": s.description,
            "decided_by": s.decided_by,
            "removable": s.required_because is None,
            "required_because": s.required_because,
            "can_escalate": s.can_escalate,
            "needs": sorted(s.needs),
            "produces": sorted(s.produces),
            "must_follow": sorted(s.must_follow),
        }
        for s in STEPS.values()
    ]
```

- [ ] **Step 4: Config — descriptions, `dump_config`, `errors_of`, `settings_schema`**

In `apps/api/app/workflow/config.py`:

1. Add `description=` to every settings field (the schema test requires it):

```python
class GatherSettings(Strict):
    priors_lookback_days: int = Field(
        180, ge=1, le=3650, description="How far back to look for prior resolutions, in days")
    # Recursion ceiling for the lineage walk.
    lineage_max_depth: int = Field(
        4, ge=1, le=4, description="Desk and entity hops to walk when tracing lineage")
    max_similar_breaks: int = Field(
        20, ge=1, le=500, description="Prior resolutions kept per book")


class ReasonSettings(Strict):
    reasoner: str = Field(
        "none",
        description="Who handles breaks the playbook cannot settle: none (a person), "
                    "session_service (the Agent SDK session service), direct (local development)")
    verdict_policy_params: list[str] = Field(
        default_factory=lambda: ["materiality_threshold", "posting_policy_reference"],
        description="Policy thresholds a POST verdict depends on; when any is unset the "
                    "POST needs controller confirmation (Rule P1)",
    )
    # keep the existing _known_reasoner validator unchanged


class ValidateSettings(Strict):
    max_hypothesis_attempts: int = Field(
        3, ge=1, le=10, description="Retries before RETRY_EXHAUSTED")


class ReviewSettings(Strict):
    max_review_cycles: int = Field(
        2, ge=1, le=10, description="Reject-and-redraft rounds before escalation")


class SessionServiceSettings(Strict):
    timeout_seconds: float = Field(
        120.0, gt=0, le=1800, description="Seconds allowed per judgement-based break")
```

2. Add imports at the top: `from typing import get_origin`, `from annotated_types import Ge, Gt, Le`, `from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator`.

3. After `settings()`, add:

```python
def dump_config(cfg: WorkflowConfig) -> dict:
    """The config as JSON-safe data, with YAML names (`validate`) and YAML order."""
    return cfg.model_dump(mode="json", by_alias=True)


def errors_of(exc: Exception) -> list[str]:
    """Every problem, one line each, in the validator's own words.

    The CLI, the API's validate endpoint and draft creation all report through
    this, so the file check and the Workflow tab can never disagree.
    """
    if not isinstance(exc, ValidationError):
        return [str(exc)]
    out: list[str] = []
    for e in exc.errors():
        msg = e["msg"].removeprefix("Value error, ")
        if msg.startswith("workflow is invalid:"):
            out += [line.strip().removeprefix("- ")
                    for line in msg.splitlines()[1:] if line.strip()]
            continue
        loc = ".".join(str(p) for p in e["loc"])
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


_TYPE_NAMES = {int: "integer", float: "number", str: "string"}


def _field_type(section: str, name: str, annotation) -> dict:
    if (section, name) == ("reason", "reasoner"):
        return {"type": "enum", "options": list(REASONERS)}
    if get_origin(annotation) is list:
        return {"type": "string_list"}
    return {"type": _TYPE_NAMES[annotation]}


def settings_schema() -> dict[str, dict[str, dict]]:
    """Each setting's type, bounds, default and description, by YAML section.

    Read from the models, so the form in the Workflow tab offers exactly the
    bounds the validator enforces.
    """
    out: dict[str, dict[str, dict]] = {}
    for attr, section_field in Settings.model_fields.items():
        section = section_field.alias or attr
        fields: dict[str, dict] = {}
        for name, f in section_field.annotation.model_fields.items():
            meta = _field_type(section, name, f.annotation) | {
                "default": f.get_default(call_default_factory=True),
                "description": f.description or "",
            }
            for m in f.metadata:
                if isinstance(m, Ge):
                    meta["min"] = m.ge
                elif isinstance(m, Gt):
                    meta["exclusive_min"] = m.gt
                elif isinstance(m, Le):
                    meta["max"] = m.le
            fields[name] = meta
        out[section] = fields
    return out
```

- [ ] **Step 5: CLI uses the shared formatter**

In `apps/api/app/workflow/cli.py`: delete `_errors` and the `import re`; import `errors_of` from `app.workflow.config`; in `_validate()` replace the loop with:

```python
        for line in errors_of(exc):
            print(f"  - {line}")
```

- [ ] **Step 6: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_catalogue.py tests/test_workflow_config.py -q` → PASS. Then the full suite → all pass. Also run `cd apps/api && .venv/bin/python -m app.workflow.cli validate` → prints `VALID`.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/workflow/registry.py apps/api/app/workflow/config.py apps/api/app/workflow/cli.py apps/api/tests/test_workflow_catalogue.py
git commit -m "feat: step catalogue with who-decides tags, settings schema from the models

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Diff and rebase

**Files:**
- Create: `apps/api/app/workflow/diff.py`
- Test: `apps/api/tests/test_workflow_diff.py`

**Interfaces:**
- Consumes: `dump_config` (Task 3) in tests only.
- Produces: `app.workflow.diff.Change` (frozen dataclass `path: str, kind: str, before=None, after=None`, method `as_dict() -> dict`); `diff(base: dict, other: dict) -> list[Change]`; `rebase(base: dict, draft: dict, active: dict) -> tuple[dict, list[str]]`. Inputs are full configs as produced by `dump_config`. Paths: `steps.<name>` (kinds `added|removed|moved`, before/after = 0-based index or None), `pause_before.<name>` (`added|removed`), `settings.<section>.<key>` (`changed`), `name`/`version` (`changed`).

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_diff.py`:

```python
"""What changed between two versions, and re-applying a stale draft."""

import copy

from app.workflow.config import dump_config, read_workflow
from app.workflow.diff import Change, diff, rebase


def _base() -> dict:
    return dump_config(read_workflow())


def _with(cfg: dict, *edits) -> dict:
    out = copy.deepcopy(cfg)
    for edit in edits:
        edit(out)
    return out


def _lookback(days):
    return lambda c: c["settings"]["gather"].update(priors_lookback_days=days)


def _move(step, to):
    def edit(c):
        c["steps"].remove(step)
        c["steps"].insert(to, step)
    return edit


def test_identical_configs_have_no_changes():
    assert diff(_base(), _base()) == []


def test_a_removed_step_names_its_old_position():
    other = _with(_base(), lambda c: c["steps"].remove("rank"))
    assert diff(_base(), other) == [Change("steps.rank", "removed", before=4, after=None)]


def test_an_added_step_names_its_new_position():
    without = _with(_base(), lambda c: c["steps"].remove("rank"))
    assert diff(without, _base()) == [Change("steps.rank", "added", before=None, after=4)]


def test_moving_one_step_reports_only_that_step():
    other = _with(_base(), _move("rank", 6))
    assert diff(_base(), other) == [Change("steps.rank", "moved", before=4, after=6)]


def test_pauses_added_and_removed():
    other = _with(_base(), lambda c: c.update(pause_before=["reason"]))
    assert diff(_base(), other) == [
        Change("pause_before.review", "removed"),
        Change("pause_before.reason", "added"),
    ]


def test_a_changed_setting_carries_both_values():
    assert diff(_base(), _with(_base(), _lookback(90))) == [
        Change("settings.gather.priors_lookback_days", "changed", before=180, after=90)
    ]


def test_changes_are_plain_dicts_for_the_api():
    assert Change("steps.rank", "removed", before=4).as_dict() == {
        "path": "steps.rank", "kind": "removed", "before": 4, "after": None,
    }


def test_rebase_keeps_the_drafts_change_and_the_active_versions_change():
    base = _base()
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    active = _with(base, _lookback(90))
    merged, conflicts = rebase(base, draft, active)
    assert "rank" not in merged["steps"]
    assert merged["settings"]["gather"]["priors_lookback_days"] == 90
    assert conflicts == []


def test_rebase_reports_a_setting_both_sides_changed_and_keeps_the_drafts_value():
    base = _base()
    merged, conflicts = rebase(base, _with(base, _lookback(30)), _with(base, _lookback(90)))
    assert merged["settings"]["gather"]["priors_lookback_days"] == 30
    assert conflicts == ["settings.gather.priors_lookback_days"]


def test_rebase_is_quiet_when_both_sides_made_the_same_change():
    base = _base()
    _, conflicts = rebase(base, _with(base, _lookback(90)), _with(base, _lookback(90)))
    assert conflicts == []


def test_rebase_reports_a_step_list_both_sides_changed():
    base = _base()
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    active = _with(base, _move("rank", 6))
    merged, conflicts = rebase(base, draft, active)
    assert "rank" not in merged["steps"] and conflicts == ["steps"]


def test_rebase_does_not_change_its_inputs():
    base, active = _base(), _with(_base(), _lookback(90))
    draft = _with(base, lambda c: c["steps"].remove("rank"))
    before = copy.deepcopy((base, draft, active))
    rebase(base, draft, active)
    assert (base, draft, active) == before
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_diff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.workflow.diff'`.

- [ ] **Step 3: Implement**

Create `apps/api/app/workflow/diff.py`:

```python
"""What changed between two workflow versions, and re-applying a stale draft.

Pure functions over full configs as dump_config produces them. The Workflow
tab shows `diff` against the active version; `rebase` rebuilds a draft whose
base is no longer active, so a controller never approves a draft that would
silently undo someone else's change.
"""

import copy
from dataclasses import asdict, dataclass

SCALARS = ("name", "version")
LISTS = ("steps", "pause_before")


@dataclass(frozen=True)
class Change:
    path: str
    kind: str  # added | removed | moved | changed
    before: object = None
    after: object = None

    def as_dict(self) -> dict:
        return asdict(self)


def _lcs(a: list, b: list) -> set:
    """Items on the longest common subsequence: the ones that did not move."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    keep, i, j = set(), 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            keep.add(a[i])
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return keep


def _step_changes(before: list, after: list) -> list[Change]:
    out = [Change(f"steps.{s}", "removed", before=before.index(s)) for s in before if s not in after]
    out += [Change(f"steps.{s}", "added", after=after.index(s)) for s in after if s not in before]
    kept_before = [s for s in before if s in after]
    kept_after = [s for s in after if s in before]
    stayed = _lcs(kept_before, kept_after)
    out += [
        Change(f"steps.{s}", "moved", before=before.index(s), after=after.index(s))
        for s in kept_after if s not in stayed
    ]
    return out


def _pause_changes(before: list, after: list) -> list[Change]:
    return (
        [Change(f"pause_before.{s}", "removed") for s in before if s not in after]
        + [Change(f"pause_before.{s}", "added") for s in after if s not in before]
    )


def _leaves(settings: dict) -> dict[str, object]:
    return {
        f"settings.{section}.{key}": value
        for section, fields in settings.items()
        for key, value in fields.items()
    }


def diff(base: dict, other: dict) -> list[Change]:
    out = [
        Change(k, "changed", before=base.get(k), after=other.get(k))
        for k in SCALARS if base.get(k) != other.get(k)
    ]
    out += _step_changes(base["steps"], other["steps"])
    out += _pause_changes(base["pause_before"], other["pause_before"])
    b, o = _leaves(base["settings"]), _leaves(other["settings"])
    out += [
        Change(path, "changed", before=b.get(path), after=o.get(path))
        for path in list(b) + [p for p in o if p not in b]
        if b.get(path) != o.get(path)
    ]
    return out


def _pick(base, draft, active) -> tuple[object, bool]:
    """The draft's value where the draft changed it, else the active one's.
    A conflict is both sides changing the same item differently."""
    if draft == base:
        return active, False
    return draft, active != base and active != draft


def rebase(base: dict, draft: dict, active: dict) -> tuple[dict, list[str]]:
    merged = copy.deepcopy(active)
    conflicts: list[str] = []
    for key in SCALARS + LISTS:
        value, clash = _pick(base.get(key), draft.get(key), active.get(key))
        merged[key] = copy.deepcopy(value)
        if clash:
            conflicts.append(key)
    b, d, a = _leaves(base["settings"]), _leaves(draft["settings"]), _leaves(active["settings"])
    settings: dict[str, dict] = {}
    for path in list(a) + [p for p in d if p not in a]:
        value, clash = _pick(b.get(path), d.get(path), a.get(path))
        _, section, name = path.split(".", 2)
        settings.setdefault(section, {})[name] = copy.deepcopy(value)
        if clash:
            conflicts.append(path)
    merged["settings"] = settings
    return merged, conflicts
```

- [ ] **Step 4: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_diff.py -q` → PASS. Full suite → all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/workflow/diff.py apps/api/tests/test_workflow_diff.py
git commit -m "feat: workflow diff and rebase

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The version store

**Files:**
- Create: `apps/api/app/workflow/versions.py`
- Test: `apps/api/tests/test_workflow_versions.py`

**Interfaces:**
- Consumes: `WorkflowVersion` (Task 2); `WorkflowConfig`, `dump_config`, `errors_of`, `read_workflow`, `workflow_path`, `REPO_ROOT` (Task 3).
- Produces (all async functions take an `AsyncSession` first):
  - Errors: `VersionError(Exception)` with class attribute `status: int`; subclasses `NotAllowed` (403), `NotFound` (404), `Conflict` (409), `Invalid` (422, attribute `errors: list[str]`).
  - `Pinned` — frozen dataclass `number: int, config: WorkflowConfig`.
  - `as_config(raw: dict) -> WorkflowConfig` (validated, cached by content).
  - `validation_errors(raw) -> list[str]` (empty when valid).
  - `ensure_seeded(s) -> None`; `active(s) -> Pinned`; `pinned(s, number: int) -> Pinned`; `config_for(s, number: int | None) -> WorkflowConfig` (None → 1); `get(s, number) -> WorkflowVersion` (NotFound); `list_versions(s) -> list[WorkflowVersion]` newest first; `pending_count(s) -> int`.
  - `create_draft(s, *, raw: dict, note: str, based_on: int, caller: Caller) -> WorkflowVersion`
  - `approve(s, number: int, *, caller: Caller, key: str) -> WorkflowVersion`
  - `reject(s, number: int, *, caller: Caller, reason: str) -> WorkflowVersion`
  - `view(row, *, with_config: bool = True) -> dict` — `{number, status, note, based_on, drafted_by, drafted_at, decided_by, decided_at, reject_reason[, config]}`, datetimes as ISO strings.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_versions.py`:

```python
"""Four-eyes workflow versions: seeded from YAML, changed only by a second approver."""

import asyncio

import pytest

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import dump_config, read_workflow

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")
ASHA = Caller(staff_id="asha", roles=["PC"], entity_scope=["LE-APAC-01"], region="APAC")
FRONT_OFFICE = Caller(staff_id="fo-user", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")


def _lookback(days: int) -> dict:
    raw = dump_config(read_workflow())
    raw["settings"]["gather"]["priors_lookback_days"] = days
    return raw


async def _draft(raw=None, *, by=PRAVEEN, based_on=1, note="change"):
    async with get_session() as s:
        return await versions.create_draft(
            s, raw=raw or _lookback(90), note=note, based_on=based_on, caller=by)


async def _approve(number, *, by=ASHA, key=None):
    async with get_session() as s:
        return await versions.approve(s, number, caller=by, key=key or f"key-{number}")


async def _reject(number, *, by=ASHA, reason="not now"):
    async with get_session() as s:
        return await versions.reject(s, number, caller=by, reason=reason)


async def test_the_yaml_seeds_version_one_as_active():
    async with get_session() as s:
        cur = await versions.active(s)
        row = await versions.get(s, 1)
    assert cur.number == 1 and cur.config == read_workflow()
    assert row.drafted_by == "system" and "fobo-investigation.yaml" in row.note


async def test_concurrent_first_reads_seed_once():
    async def read():
        async with get_session() as s:
            return (await versions.active(s)).number

    assert await asyncio.gather(*(read() for _ in range(5))) == [1] * 5
    async with get_session() as s:
        assert len(await versions.list_versions(s)) == 1


async def test_a_draft_is_saved_with_who_and_why():
    d = await _draft(note="Lookback 180→90 days")
    assert (d.number, d.status, d.based_on, d.drafted_by) == (2, "draft", 1, "praveen")
    assert d.config["settings"]["gather"]["priors_lookback_days"] == 90


async def test_an_invalid_draft_lists_every_problem():
    raw = _lookback(90)
    raw["steps"].remove("reason")
    raw["steps"].remove("validate")
    with pytest.raises(versions.Invalid) as exc:
        await _draft(raw)
    assert any("'reason' cannot be removed" in e for e in exc.value.errors)
    assert any("'validate' cannot be removed" in e for e in exc.value.errors)


async def test_a_draft_needs_a_note():
    with pytest.raises(versions.Invalid, match="note"):
        await _draft(note="   ")


async def test_a_note_over_the_limit_is_refused():
    with pytest.raises(versions.Invalid, match="500"):
        await _draft(note="x" * 501)


async def test_only_product_control_can_draft():
    with pytest.raises(versions.NotAllowed):
        await _draft(by=FRONT_OFFICE)


async def test_a_draft_must_be_based_on_a_real_version():
    with pytest.raises(versions.NotFound):
        await _draft(based_on=99)


async def test_approval_activates_the_draft_and_supersedes_the_old_one():
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert (await versions.active(s)).number == 2
        assert (await versions.get(s, 1)).status == "superseded"
        row = await versions.get(s, 2)
    assert row.decided_by == "asha" and row.decided_at is not None


async def test_the_drafter_cannot_approve_their_own_draft():
    d = await _draft(by=PRAVEEN)
    with pytest.raises(versions.NotAllowed, match="second"):
        await _approve(d.number, by=PRAVEEN)


async def test_only_product_control_can_approve():
    d = await _draft()
    with pytest.raises(versions.NotAllowed):
        await _approve(d.number, by=FRONT_OFFICE)


async def test_a_stale_draft_cannot_be_approved():
    first, second = await _draft(_lookback(90)), await _draft(_lookback(30))
    await _approve(first.number)
    with pytest.raises(versions.Conflict, match="v2 went live"):
        await _approve(second.number)


async def test_a_version_cannot_be_approved_twice():
    d = await _draft()
    await _approve(d.number, key="a")
    with pytest.raises(versions.Conflict):
        await _approve(d.number, key="b")


async def test_an_idempotency_key_is_used_once():
    first = await _draft()
    await _approve(first.number, key="same")
    second = await _draft(based_on=first.number)
    with pytest.raises(versions.Conflict, match="already recorded"):
        await _approve(second.number, key="same")


async def test_an_approval_needs_a_key():
    d = await _draft()
    with pytest.raises(versions.Invalid):
        await _approve(d.number, key="  ")


async def test_two_approvals_racing_leave_exactly_one_active():
    a, b = await _draft(_lookback(90)), await _draft(_lookback(30))
    results = await asyncio.gather(
        _approve(a.number, key="ka"), _approve(b.number, key="kb"), return_exceptions=True)
    assert sum(isinstance(r, versions.Conflict) for r in results) == 1
    async with get_session() as s:
        assert [v.status for v in await versions.list_versions(s)].count("active") == 1


async def test_a_rejection_needs_a_reason():
    d = await _draft()
    with pytest.raises(versions.Invalid):
        await _reject(d.number, reason=" ")


async def test_a_rejection_keeps_who_and_why():
    d = await _draft()
    await _reject(d.number, reason="too aggressive")
    async with get_session() as s:
        row = await versions.get(s, d.number)
    assert (row.status, row.reject_reason, row.decided_by) == ("rejected", "too aggressive", "asha")


async def test_the_drafter_may_withdraw_their_own_draft():
    d = await _draft(by=PRAVEEN)
    assert (await _reject(d.number, by=PRAVEEN)).status == "rejected"


async def test_a_decided_version_cannot_be_rejected():
    d = await _draft()
    await _approve(d.number)
    with pytest.raises(versions.Conflict):
        await _reject(d.number)


async def test_nothing_is_ever_deleted_and_pending_counts_drafts():
    a = await _draft()
    b = await _draft(_lookback(30))
    await _reject(b.number)
    await _draft(_lookback(45))
    async with get_session() as s:
        assert [v.number for v in await versions.list_versions(s)] == [4, 3, 2, 1]
        assert await versions.pending_count(s) == 2
    assert a.number == 2


async def test_an_approval_is_seen_by_the_next_read_without_a_restart():
    async with get_session() as s:
        assert (await versions.active(s)).config.settings.gather.priors_lookback_days == 180
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert (await versions.active(s)).config.settings.gather.priors_lookback_days == 90


async def test_a_run_without_a_version_reads_version_one():
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert await versions.config_for(s, None) == read_workflow()


async def test_the_view_is_json_ready():
    d = await _draft()
    v = versions.view(d)
    assert v["number"] == 2 and isinstance(v["drafted_at"], str)
    assert list(v["config"]) == ["version", "name", "steps", "pause_before", "settings"]
    assert "config" not in versions.view(d, with_config=False)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_versions.py -q`
Expected: FAIL — `ImportError: cannot import name 'versions'`.

- [ ] **Step 3: Implement**

Create `apps/api/app/workflow/versions.py`:

```python
"""Workflow versions — the database decides which workflow runs.

The checked-in YAML seeds version 1. After that the workflow changes only
through a draft that a *second* Product Control user approves; approval
activates it for new runs, and a run keeps the version it started with
(app/workflow/graph.py). Nothing is ever deleted.

Every rule here is enforced server-side; the Workflow tab only reflects them.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.db.models_workflow import WorkflowVersion
from app.workflow.config import (
    REPO_ROOT,
    WorkflowConfig,
    dump_config,
    errors_of,
    read_workflow,
    workflow_path,
)

SYSTEM = "system"
PC_ROLE = "PC"
NOTE_MAX = 500
# Distinct from api/deps.py SEED_LOCK_KEY (872155).
WORKFLOW_LOCK_KEY = 872156


class VersionError(Exception):
    status = 400


class NotAllowed(VersionError):
    status = 403


class NotFound(VersionError):
    status = 404


class Conflict(VersionError):
    status = 409


class Invalid(VersionError):
    status = 422

    def __init__(self, message: str, errors=()):
        super().__init__(message)
        self.errors = list(errors)


@dataclass(frozen=True)
class Pinned:
    number: int
    config: WorkflowConfig


@lru_cache(maxsize=64)
def _validated(config_json: str) -> WorkflowConfig:
    return WorkflowConfig.model_validate(json.loads(config_json))


def as_config(raw: dict) -> WorkflowConfig:
    """Validated config for stored JSON. Cached by content, so a version's
    config is validated once per process however often it is read."""
    return _validated(json.dumps(raw, sort_keys=True))


def validation_errors(raw) -> list[str]:
    try:
        WorkflowConfig.model_validate(raw)
    except (ValidationError, ValueError) as exc:
        return errors_of(exc)
    return []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_note() -> str:
    path = workflow_path()
    try:
        shown = path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        shown = path
    return f"seeded from {shown}"


async def _lock(s) -> None:
    """Transaction-scoped: released by the commit or rollback that ends it."""
    await s.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": WORKFLOW_LOCK_KEY})


async def _count(s) -> int:
    return await s.scalar(select(func.count()).select_from(WorkflowVersion))


async def ensure_seeded(s) -> None:
    if await _count(s):
        return
    await _lock(s)
    if not await _count(s):
        now = _now()
        s.add(WorkflowVersion(
            number=1, config=dump_config(read_workflow()), status="active",
            based_on=None, note=_seed_note(), drafted_by=SYSTEM, drafted_at=now,
            decided_by=SYSTEM, decided_at=now,
        ))
    await s.commit()


async def get(s, number: int) -> WorkflowVersion:
    row = await s.get(WorkflowVersion, number)
    if row is None:
        raise NotFound(f"no workflow version {number}")
    return row


async def _active_row(s) -> WorkflowVersion:
    return await s.scalar(select(WorkflowVersion).where(WorkflowVersion.status == "active"))


async def active(s) -> Pinned:
    await ensure_seeded(s)
    row = await _active_row(s)
    return Pinned(row.number, as_config(row.config))


async def pinned(s, number: int) -> Pinned:
    await ensure_seeded(s)
    return Pinned(number, as_config((await get(s, number)).config))


async def config_for(s, number: int | None) -> WorkflowConfig:
    """A run's workflow. None: the run predates versioning — version 1."""
    return (await pinned(s, number or 1)).config


async def list_versions(s) -> list[WorkflowVersion]:
    await ensure_seeded(s)
    rows = await s.scalars(select(WorkflowVersion).order_by(WorkflowVersion.number.desc()))
    return list(rows.all())


async def pending_count(s) -> int:
    return await s.scalar(
        select(func.count()).select_from(WorkflowVersion).where(WorkflowVersion.status == "draft"))


def _require_pc(caller) -> None:
    if PC_ROLE not in caller.roles:
        raise NotAllowed("only Product Control can change the workflow")


def _clean_note(note: str | None) -> str:
    n = (note or "").strip()
    if not n:
        raise Invalid("a note is required: say why the workflow is changing")
    if len(n) > NOTE_MAX:
        raise Invalid(f"the note is {len(n)} characters; the limit is {NOTE_MAX}")
    return n


async def create_draft(s, *, raw: dict, note: str, based_on: int, caller) -> WorkflowVersion:
    _require_pc(caller)
    clean = _clean_note(note)
    errors = validation_errors(raw)
    if errors:
        raise Invalid("workflow is invalid", errors)
    await ensure_seeded(s)
    await get(s, based_on)
    await _lock(s)
    number = (await s.scalar(select(func.max(WorkflowVersion.number)))) + 1
    row = WorkflowVersion(
        number=number, config=dump_config(WorkflowConfig.model_validate(raw)),
        status="draft", based_on=based_on, note=clean,
        drafted_by=caller.staff_id, drafted_at=_now(),
    )
    s.add(row)
    await s.commit()
    return row


async def _decidable(s, number: int) -> WorkflowVersion:
    row = await get(s, number)
    if row.status != "draft":
        raise Conflict(f"v{number} is {row.status}, not a draft")
    return row


async def approve(s, number: int, *, caller, key: str) -> WorkflowVersion:
    _require_pc(caller)
    if not (key or "").strip():
        raise Invalid("an Idempotency-Key header is required")
    await _lock(s)
    used = await s.scalar(select(WorkflowVersion.number).where(WorkflowVersion.decision_key == key))
    if used is not None:
        raise Conflict("this approval was already recorded")
    row = await _decidable(s, number)
    if row.drafted_by == caller.staff_id:
        raise NotAllowed("a second Product Control user must approve — you drafted this version")
    current = await _active_row(s)
    if current.number != row.based_on:
        raise Conflict(f"v{current.number} went live after this was drafted — "
                       f"redraft it on v{current.number}")
    current.status = "superseded"
    # Flush first: the partial unique index allows one active row at a time.
    await s.flush()
    row.status, row.decided_by, row.decided_at, row.decision_key = (
        "active", caller.staff_id, _now(), key)
    await s.commit()
    return row


async def reject(s, number: int, *, caller, reason: str) -> WorkflowVersion:
    _require_pc(caller)
    clean = (reason or "").strip()
    if not clean:
        raise Invalid("a rejection requires a reason")
    await _lock(s)
    row = await _decidable(s, number)
    row.status, row.decided_by, row.decided_at, row.reject_reason = (
        "rejected", caller.staff_id, _now(), clean)
    await s.commit()
    return row


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def view(row: WorkflowVersion, *, with_config: bool = True) -> dict:
    body = {
        "number": row.number,
        "status": row.status,
        "note": row.note,
        "based_on": row.based_on,
        "drafted_by": row.drafted_by,
        "drafted_at": _iso(row.drafted_at),
        "decided_by": row.decided_by,
        "decided_at": _iso(row.decided_at),
        "reject_reason": row.reject_reason,
    }
    if with_config:
        # Re-dumped through the model: JSONB does not keep key order.
        body["config"] = dump_config(as_config(row.config))
    return body
```

- [ ] **Step 4: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_versions.py -q` → PASS. Full suite → all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/workflow/versions.py apps/api/tests/test_workflow_versions.py
git commit -m "feat: workflow version store — drafts, second-approver activation, rejection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Pin each run to its version

**Files:**
- Modify: `apps/api/app/workflow/config.py` (`use_workflow`, `settings()`, `workflow()` docstring)
- Modify: `apps/api/app/workflow/graph.py`
- Modify: `apps/api/app/workflow/session.py`
- Modify: `apps/api/app/workflow/state.py`
- Modify: `apps/api/app/queries/trace.py`
- Modify: `apps/api/api/cases.py`, `apps/api/api/routes/decisions.py` (the `build_graph(...).aget_state` read, ~line 74), `apps/api/api/routes/sessions.py` (`load_snapshot`), `apps/api/api/routes/helix.py` (`ask`)
- Modify: `config/workflow/fobo-investigation.yaml` (header comment only)
- Test: `apps/api/tests/test_workflow_pinning.py`

**Interfaces:**
- Consumes: `versions.active`, `versions.pinned`, `versions.Pinned`, `versions.create_draft`, `versions.approve` (Task 5).
- Produces: `app.workflow.config.use_workflow(cfg)` (context manager); `settings()` returns the bound config's settings, else the YAML file's. `app.workflow.graph.pinned_for_session(session, thread_id: str) -> Pinned`; `graph_for_session(checkpointer, session, thread_id: str) -> tuple[CompiledGraph, Pinned]`. `InvestigationState.workflow_version: int`. Trace response `workflow_version` becomes the version **number** (int) and is also present when `status == "not_started"`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_pinning.py`:

```python
"""A run keeps the workflow version it started with."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from api.main import create_app
from app.contracts.models import Caller
from app.db.base import get_session
from app.db.models_ops import SourceCall
from app.db.models_session import InvestigationSession
from app.workflow import versions
from app.workflow.config import (
    WorkflowConfig,
    dump_config,
    read_workflow,
    settings,
    use_workflow,
)
from app.workflow.graph import pinned_for_session

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")
ASHA = Caller(staff_id="asha", roles=["PC"], entity_scope=["LE-APAC-01"], region="APAC")


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def _activate_v2_without_rank_and_a_30_day_lookback():
    async with get_session() as s:
        raw = dump_config((await versions.active(s)).config)
        raw["steps"].remove("rank")
        raw["settings"]["gather"]["priors_lookback_days"] = 30
        draft = await versions.create_draft(
            s, raw=raw, note="drop rank, 30-day lookback", based_on=1, caller=PRAVEEN)
    async with get_session() as s:
        await versions.approve(s, draft.number, caller=ASHA, key="pin-test")


async def _lookbacks(session_id: str) -> list[str]:
    async with get_session() as s:
        params = await s.scalars(
            select(SourceCall.validated_parameters).where(
                SourceCall.investigation_session_id == session_id,
                SourceCall.tool_name == "helix.similar_breaks",
            ))
        return [p["lookback"] for p in params]


async def _trace(client, rec: str) -> dict:
    return (await client.get(f"/api/recs/{rec}/trace")).json()["trace"]


async def test_a_run_started_on_v1_keeps_v1_after_v2_goes_live(client):
    await client.get("/api/recs/R-1055")
    await _activate_v2_without_rank_and_a_30_day_lookback()
    trace = await _trace(client, "R-1055")
    assert trace["workflow_version"] == 1
    assert "rank" in [s["node"] for s in trace["steps"]]
    assert await _lookbacks("sess-r-1055") == ["180d"]


async def test_a_run_started_after_the_approval_runs_v2(client):
    await _activate_v2_without_rank_and_a_30_day_lookback()
    await client.get("/api/recs/R-2031")
    trace = await _trace(client, "R-2031")
    assert trace["workflow_version"] == 2
    assert "rank" not in [s["node"] for s in trace["steps"]]
    # gather reads settings() inside a LangGraph step: the ContextVar reached it.
    assert await _lookbacks("sess-r-2031") == ["30d"]


async def test_the_run_records_its_version_on_the_session_row(client):
    await client.get("/api/recs/R-1055")
    async with get_session() as s:
        row = await s.get(InvestigationSession, "sess-r-1055")
    assert row.workflow_version == 1


async def test_a_run_from_before_versioning_is_read_as_v1(client):
    await client.get("/api/recs/R-1055")
    async with get_session() as s:
        await s.execute(update(InvestigationSession)
                        .where(InvestigationSession.investigation_session_id == "sess-r-1055")
                        .values(workflow_version=None))
        await s.commit()
    await _activate_v2_without_rank_and_a_30_day_lookback()
    trace = await _trace(client, "R-1055")
    assert trace["workflow_version"] == 1 and trace["status"] == "awaiting_signoff"


async def test_a_run_that_has_not_started_is_shown_with_the_active_workflow():
    await _activate_v2_without_rank_and_a_30_day_lookback()
    async with get_session() as s:
        assert (await pinned_for_session(s, "sess-never-ran")).number == 2


def test_outside_a_run_settings_come_from_the_file():
    assert settings() == read_workflow().settings


def test_inside_use_workflow_settings_are_the_bound_ones():
    raw = dump_config(read_workflow())
    raw["settings"]["gather"]["priors_lookback_days"] = 7
    with use_workflow(WorkflowConfig.model_validate(raw)):
        assert settings().gather.priors_lookback_days == 7
    assert settings().gather.priors_lookback_days == 180
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_pinning.py -q`
Expected: FAIL — `ImportError: cannot import name 'use_workflow'`.

- [ ] **Step 3: Bind a run's workflow**

In `apps/api/app/workflow/config.py` add `from contextlib import contextmanager` and `from contextvars import ContextVar` to the imports. Replace `workflow()`'s docstring and `settings()` with:

```python
@lru_cache(maxsize=1)
def workflow() -> WorkflowConfig:
    """The YAML file's workflow: the seed for version 1, and what settings()
    falls back to outside a run. The API runs whichever version is active in
    the database (app/workflow/versions.py)."""
    return read_workflow()


def reset_workflow_cache() -> None:
    workflow.cache_clear()


# The workflow of the run executing in this context. run_investigation binds
# the run's pinned version for the length of the run; LangGraph copies the
# context into the tasks that execute each step, so every step reads it.
_bound: ContextVar["WorkflowConfig | None"] = ContextVar("fobo_workflow", default=None)


@contextmanager
def use_workflow(cfg: "WorkflowConfig"):
    token = _bound.set(cfg)
    try:
        yield cfg
    finally:
        _bound.reset(token)


def settings() -> Settings:
    """The running workflow's settings: the run's pinned version inside a
    run; the YAML file's outside one (the CLI, and unit tests that call a
    step directly)."""
    return (_bound.get() or workflow()).settings
```

- [ ] **Step 4: Pin in the graph module**

In `apps/api/app/workflow/graph.py`: change the config import to `from app.workflow.config import WorkflowConfig, use_workflow, workflow`, add `from sqlalchemy import select` and `from app.db.models_session import InvestigationSession`, and replace `run_investigation` and `resume_investigation` with:

```python
async def pinned_for_session(session, thread_id: str):
    """The workflow a run started with, from its investigation_session row.

    No row: the run has not started, so it is shown with the workflow that
    would run now. A row without a version predates versioning: version 1.
    A column select, not session.get, so a row updated by a Core upsert is
    never read stale from the identity map.
    """
    from app.workflow import versions

    row = (await session.execute(
        select(InvestigationSession.investigation_session_id,
               InvestigationSession.workflow_version)
        .where(InvestigationSession.investigation_session_id == thread_id)
    )).first()
    if row is None:
        return await versions.active(session)
    return await versions.pinned(session, row.workflow_version or 1)


async def graph_for_session(checkpointer, session, thread_id: str):
    """The run's own graph, built from the version it was pinned to."""
    pinned = await pinned_for_session(session, thread_id)
    return build_graph(checkpointer, session=session, config=pinned.config), pinned


async def run_investigation(state, *, thread_id, session, checkpointer):
    from app.workflow import versions

    # The run is pinned to the version active now, for its whole life.
    pinned = await versions.active(session)
    state = {**state, "workflow_version": pinned.number}
    # source_call carries an FK to the session, and gather records as it
    # retrieves, so the row has to exist before the graph starts.
    await ensure_investigation_session(session, state)
    app = build_graph(checkpointer, session=session, config=pinned.config)
    config = {"configurable": {"thread_id": thread_id}}
    with use_workflow(pinned.config):
        await app.ainvoke(state, config)
    return (await app.aget_state(config)).values


async def resume_investigation(thread_id, decisions, *, session, checkpointer):
    app, pinned = await graph_for_session(checkpointer, session, thread_id)
    config = {"configurable": {"thread_id": thread_id}}
    with use_workflow(pinned.config):
        await app.aupdate_state(config, {"decisions": decisions})
        await app.ainvoke(None, config)
    return (await app.aget_state(config)).values
```

- [ ] **Step 5: Record the version on the session row**

In `apps/api/app/workflow/session.py`, replace the statement and extend the docstring:

```python
async def ensure_investigation_session(session, state: InvestigationState) -> None:
    """Idempotent insert.

    ON CONFLICT rather than a read-then-write: the console fires two
    investigates at once in dev (React StrictMode), and a check-then-act
    lets both see no row and both insert. The primary key is the authority.

    A row created earlier without a workflow version (a recorded session, or
    a run from before versioning) takes the version of the run starting now.
    Once set, a run's version never changes.
    """
    version = state.get("workflow_version")
    stmt = (
        insert(InvestigationSession)
        .values(
            investigation_session_id=state["investigation_session_id"],
            reconciliation_id=state["reconciliation_id"],
            master_book=state["master_book"],
            business_date=state["business_date"],
            run_id=state["run_id"],
            status="analysing",
            workflow_version=version,
        )
        .on_conflict_do_update(
            index_elements=["investigation_session_id"],
            set_={"workflow_version": version},
            where=InvestigationSession.workflow_version.is_(None),
        )
    )
    await session.execute(stmt)
    await session.commit()
```

In `apps/api/app/workflow/state.py`, add under `# Identity`: `workflow_version: int`.

- [ ] **Step 6: Every checkpoint reader uses the run's own graph**

`apps/api/api/cases.py` — import `graph_for_session, run_investigation` from `app.workflow.graph` (drop `build_graph` if now unused) and replace the two graph reads:

```python
    async with _opening[rec.rec_id]:
        async with checkpointer() as cp:
            graph, _ = await graph_for_session(cp, s, sid)
            snapshot = await graph.aget_state(config)
            if not snapshot.values:
                await run_investigation(
                    initial_state(rec, run, breaks),
                    thread_id=sid,
                    session=s,
                    checkpointer=cp,
                )
                # Nodes after group record calls without committing; the
                # checkpoint is durable, so their rows must be too, or a later
                # read finds a finished investigation missing its last calls.
                await s.commit()
                graph, _ = await graph_for_session(cp, s, sid)
                snapshot = await graph.aget_state(config)
    return snapshot


async def read_case(s, rec_id: str):
    """The checkpointed state only; never runs anything."""
    sid = session_id_for(rec_id)
    async with checkpointer() as cp:
        graph, _ = await graph_for_session(cp, s, sid)
        snapshot = await graph.aget_state({"configurable": {"thread_id": sid}})
    return snapshot if snapshot.values else None
```

`apps/api/api/routes/decisions.py` — replace the checkpoint read (currently `snapshot = await build_graph(cp, session=s).aget_state(...)`) with:

```python
    async with checkpointer() as cp:
        graph, _ = await graph_for_session(cp, s, sid)
        snapshot = await graph.aget_state({"configurable": {"thread_id": sid}})
```

and import `graph_for_session` from `app.workflow.graph` (remove the `build_graph` import if unused).

`apps/api/api/routes/sessions.py` — `load_snapshot` becomes:

```python
async def load_snapshot(session_id: str):
    async with get_session() as s:
        async with checkpointer() as cp:
            graph, _ = await graph_for_session(cp, s, session_id)
            return await graph.aget_state({"configurable": {"thread_id": session_id}})
```

(import `graph_for_session, run_investigation`; drop `build_graph` if unused).

`apps/api/api/routes/helix.py` — in `ask`, replace `reasoner=settings().reason.reasoner,` with a read of the active version:

```python
        active = await versions.active(s)
        tools = SessionTools(s, sid, workspace(view, business_date))
        intent, blocks = await answer(
            view, question, tools, cob=str(business_date),
            analysis_call_ids=[c["id"] for c in view["calls"]],
            reasoner=active.config.settings.reason.reasoner,
        )
```

Add `from app.workflow import versions`; remove `from app.workflow.config import settings` if nothing else in the file uses it.

- [ ] **Step 7: The trace reads the run's version**

In `apps/api/app/queries/trace.py`, replace the imports and `_workflow()` with:

```python
from app.workflow.graph import graph_for_session
from app.workflow.registry import STEPS


def _steps(cfg) -> list[tuple[str, str, str]]:
    """The run's configured steps, in order — so the trace shows the workflow
    that actually ran, including steps that have not run yet."""
    return [(n, STEPS[n].label, STEPS[n].description) for n in cfg.steps]
```

and in `execution_trace`: start with `graph, pinned = await graph_for_session(checkpointer, session, thread_id)`; replace every `_workflow()` with `_steps(pinned.config)`; in the not-started return add `"workflow_version": pinned.number,`; delete the late `from app.workflow.config import workflow`; in the final return use `"workflow_version": pinned.number,` and `"pause_before": list(pinned.config.pause_before),`.

- [ ] **Step 8: Correct the YAML header**

In `config/workflow/fobo-investigation.yaml`, replace the "To change the workflow" block (lines starting `# To change the workflow:` through `# already in flight keep the one they started with.`) with:

```yaml
# The running API does not read this file. It reads the active version from
# the database: this file seeds version 1 on a fresh database, and is the
# format of Download / Upload YAML in the console's Workflow tab.
#
# To change the live workflow, use the Workflow tab: a draft becomes active
# only when a second Product Control user approves it. New investigations
# use the new version; a run keeps the version it started with.
#
# To check an edit to this file:
#   apps/api/.venv/bin/python -m app.workflow.cli validate
```

- [ ] **Step 9: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_pinning.py tests/test_trace.py tests/test_checkpoint_resume.py tests/test_decisions.py -q` → PASS. Full suite → all pass.

- [ ] **Step 10: Commit**

```bash
git add apps/api/app apps/api/api apps/api/tests/test_workflow_pinning.py config/workflow/fobo-investigation.yaml
git commit -m "feat: each run is pinned to the workflow version it started with

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: YAML export and parsing

**Files:**
- Create: `apps/api/app/workflow/yaml_io.py`
- Test: `apps/api/tests/test_workflow_yaml.py`

**Interfaces:**
- Consumes: `WorkflowConfig`, `dump_config` (Task 3); `versions.get`, `versions.active`, `versions.create_draft` (Task 5) in tests.
- Produces: `app.workflow.yaml_io.MAX_BYTES = 65536`; `YamlError(ValueError)` with `line: int | None`, `column: int | None`; `to_yaml(row) -> str`; `parse_yaml(text: str) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_yaml.py`:

```python
"""Download a version as YAML, upload YAML as a draft."""

import pytest
import yaml

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import dump_config, read_workflow
from app.workflow.yaml_io import MAX_BYTES, YamlError, parse_yaml, to_yaml

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")


async def _seed_row():
    async with get_session() as s:
        await versions.active(s)
        return await versions.get(s, 1)


async def test_a_version_round_trips_through_yaml():
    text = to_yaml(await _seed_row())
    assert parse_yaml(text) == dump_config(read_workflow())


async def test_the_export_keeps_the_repo_files_key_order_despite_jsonb():
    body = yaml.safe_load(to_yaml(await _seed_row()))
    assert list(body) == ["version", "name", "steps", "pause_before", "settings"]


async def test_the_export_says_which_version_and_who():
    text = to_yaml(await _seed_row())
    assert text.startswith("# FOBO investigation workflow, version 1 (active)")
    assert "approved by system" in text


async def test_a_multi_line_note_stays_one_comment_line():
    raw = dump_config(read_workflow())
    async with get_session() as s:
        row = await versions.create_draft(s, raw=raw, note="line one\nline two",
                                          based_on=1, caller=PRAVEEN)
    text = to_yaml(row)
    assert "# Note: line one line two" in text
    assert parse_yaml(text) == raw


def test_unreadable_yaml_names_the_line_and_column():
    with pytest.raises(YamlError) as exc:
        parse_yaml("steps: [resolve,\n  gather\nname: x: y\n")
    assert exc.value.line is not None
    assert str(exc.value).startswith(f"line {exc.value.line}, column ")


def test_a_list_is_not_a_workflow():
    with pytest.raises(YamlError, match="mapping"):
        parse_yaml("- resolve\n- gather\n")


def test_an_oversized_file_is_refused():
    with pytest.raises(YamlError, match="64 KB"):
        parse_yaml("#" * (MAX_BYTES + 1))
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_yaml.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.workflow.yaml_io'`.

- [ ] **Step 3: Implement**

Create `apps/api/app/workflow/yaml_io.py`:

```python
"""YAML in and out of the Workflow tab, in the same layout as the repo file."""

import yaml

from app.workflow.config import WorkflowConfig, dump_config

MAX_BYTES = 64 * 1024


class YamlError(ValueError):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.line = line
        self.column = column


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())


def _decision(row) -> str:
    if not row.decided_by:
        return ""
    verb = "rejected" if row.status == "rejected" else "approved"
    return f"; {verb} by {row.decided_by}"


def to_yaml(row) -> str:
    # Through the model: JSONB does not keep key order, the model does.
    config = dump_config(WorkflowConfig.model_validate(row.config))
    header = [
        f"# FOBO investigation workflow, version {row.number} ({row.status})",
        f"# Drafted by {row.drafted_by}{_decision(row)}.",
        f"# Note: {_one_line(row.note)}",
        "#",
        "# Upload this file in the Workflow tab to propose it as a draft; a second",
        "# Product Control user must approve it before new runs use it.",
        "",
    ]
    body = yaml.safe_dump(config, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return "\n".join(header) + body


def parse_yaml(text: str) -> dict:
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise YamlError(f"the file is {size} bytes; the limit is 64 KB")
    try:
        raw = yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        if mark is None:
            raise YamlError(str(exc)) from exc
        line, column = mark.line + 1, mark.column + 1
        problem = exc.problem or exc.context or "not valid YAML"
        raise YamlError(f"line {line}, column {column}: {problem}", line, column) from exc
    except yaml.YAMLError as exc:
        raise YamlError(str(exc)) from exc
    if not isinstance(raw, dict):
        raise YamlError("the file must be a YAML mapping with steps, pause_before and settings")
    return raw
```

- [ ] **Step 4: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_yaml.py -q` → PASS. Full suite → all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/workflow/yaml_io.py apps/api/tests/test_workflow_yaml.py
git commit -m "feat: workflow YAML export and parsing with line-numbered errors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The `/api/workflow` endpoints

**Files:**
- Create: `apps/api/api/routes/workflow.py`
- Modify: `apps/api/api/main.py`
- Test: `apps/api/tests/test_workflow_api.py`

**Interfaces:**
- Consumes: `current_caller`, `dev_callers` (Task 1); `catalogue` (Task 3); `settings_schema`, `REASONERS`, `dump_config` (Task 3); `diff`, `rebase` (Task 4); everything in `versions` (Task 5); `to_yaml`, `parse_yaml`, `YamlError` (Task 7).
- Produces: the HTTP contract in spec §4. Validation failures: `detail = {"message": str, "errors": list[str]}`; other errors: `detail = str`.

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_workflow_api.py`:

```python
"""The Workflow tab's API."""

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import create_app
from app.workflow.config import dump_config, read_workflow
from app.workflow.versions import validation_errors

ASHA = {"X-Dev-Caller": "asha"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("FOBO_ENV", "dev")
    monkeypatch.delenv("FOBO_REASONER", raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test") as c:
        yield c


def _config(*edits) -> dict:
    raw = dump_config(read_workflow())
    for edit in edits:
        edit(raw)
    return raw


def _lookback(days):
    return _config(lambda r: r["settings"]["gather"].update(priors_lookback_days=days))


async def _draft(client, config=None, *, note="Lookback 180→90 days", based_on=1, headers=None):
    return await client.post("/api/workflow/drafts", headers=headers or {},
                             json={"config": config or _lookback(90), "note": note,
                                   "based_on": based_on})


async def _approve(client, number, *, key="k1", headers=ASHA):
    return await client.post(f"/api/workflow/versions/{number}/approve",
                             headers={"Idempotency-Key": key, **headers})


async def test_the_overview_serves_the_active_version_and_the_catalogue(client):
    body = (await client.get("/api/workflow")).json()
    assert (body["active"]["number"], body["active"]["status"]) == (1, "active")
    assert body["active"]["config"]["steps"] == read_workflow().steps
    assert [s["name"] for s in body["steps"]][:3] == ["resolve", "gather", "group"]
    assert body["settings_schema"]["gather"]["lineage_max_depth"]["max"] == 4
    assert body["reasoners"] == ["none", "session_service", "direct"]
    assert body["overrides"] == {} and body["pending_drafts"] == 0
    assert body["caller"] == {"id": "praveen", "roles": ["FO", "PC"]}
    assert [c["id"] for c in body["dev_callers"]] == ["praveen", "asha"]


async def test_outside_dev_no_dev_callers_are_offered(client, monkeypatch):
    monkeypatch.delenv("FOBO_ENV")
    assert "dev_callers" not in (await client.get("/api/workflow")).json()


async def test_a_reasoner_override_is_reported(client, monkeypatch):
    monkeypatch.setenv("FOBO_REASONER", "direct")
    assert (await client.get("/api/workflow")).json()["overrides"] == {"reasoner": "direct"}


def _move_draft_early(r):
    r["steps"].remove("draft")
    r["steps"].insert(2, "draft")


BAD = [
    (lambda r: r["steps"].remove("reason"), "'reason' cannot be removed"),
    (_move_draft_early, "'draft' needs 'pattern_groups'"),
    (lambda r: r["steps"].__setitem__(1, "gathr"), "'gathr' is not a known step"),
    (lambda r: r.update(pause_before=[]), "must include 'review'"),
    (lambda r: r["settings"]["gather"].update(prior_lookback_days=90), "prior_lookback_days"),
    # A cleared number field in the form arrives as "".
    (lambda r: r["settings"]["gather"].update(priors_lookback_days=""), "priors_lookback_days"),
]


@pytest.mark.parametrize("edit, phrase", BAD)
async def test_validate_reports_exactly_what_the_file_check_reports(client, edit, phrase):
    raw = _config(edit)
    r = await client.post("/api/workflow/validate", json={"config": raw})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["errors"] == validation_errors(raw)
    assert any(phrase in e for e in body["errors"])


async def test_a_valid_config_validates(client):
    assert (await client.post("/api/workflow/validate", json={"config": _lookback(90)})).json() == {
        "ok": True, "errors": []}


async def test_a_draft_is_created_and_counted(client):
    r = await _draft(client)
    assert r.status_code == 201
    v = r.json()
    assert (v["number"], v["status"], v["drafted_by"], v["based_on"]) == (2, "draft", "praveen", 1)
    assert (await client.get("/api/workflow")).json()["pending_drafts"] == 1


async def test_an_invalid_draft_is_a_422_listing_every_problem(client):
    r = await _draft(client, _config(lambda c: c["steps"].remove("reason"),
                                     lambda c: c["steps"].remove("validate")))
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["message"] == "workflow is invalid" and len(detail["errors"]) >= 2


async def test_a_cleared_number_field_cannot_be_saved(client):
    r = await _draft(client, _config(
        lambda c: c["settings"]["gather"].update(priors_lookback_days="")))
    assert r.status_code == 422


async def test_a_draft_needs_a_note(client):
    r = await _draft(client, note="")
    assert r.status_code == 422 and "note" in r.json()["detail"]


async def test_the_drafter_cannot_approve(client):
    number = (await _draft(client)).json()["number"]
    r = await _approve(client, number, headers={})
    assert r.status_code == 403 and "second" in r.json()["detail"]


async def test_a_second_pc_user_activates_the_draft(client):
    number = (await _draft(client)).json()["number"]
    r = await _approve(client, number)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["decided_by"]) == ("active", "asha")
    overview = (await client.get("/api/workflow")).json()
    assert overview["active"]["number"] == number
    assert overview["active"]["config"]["settings"]["gather"]["priors_lookback_days"] == 90
    history = (await client.get("/api/workflow/versions")).json()
    assert [(v["number"], v["status"]) for v in history] == [(2, "active"), (1, "superseded")]
    assert "config" not in history[0]


async def test_an_approval_needs_an_idempotency_key(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/approve", headers=ASHA)
    assert r.status_code == 422


async def test_a_reused_key_is_refused(client):
    first = (await _draft(client)).json()["number"]
    await _approve(client, first, key="same")
    second = (await _draft(client, _lookback(30), based_on=first)).json()["number"]
    r = await _approve(client, second, key="same")
    assert r.status_code == 409 and "already recorded" in r.json()["detail"]


async def test_approving_twice_is_refused(client):
    number = (await _draft(client)).json()["number"]
    await _approve(client, number, key="a")
    assert (await _approve(client, number, key="b")).status_code == 409


async def test_a_stale_draft_is_refused_and_can_be_rebased(client):
    a = (await _draft(client, _lookback(90))).json()["number"]
    b = (await _draft(client, _config(lambda c: c["steps"].remove("rank")),
                      note="drop rank")).json()["number"]
    await _approve(client, a, key="ka")
    r = await _approve(client, b, key="kb")
    assert r.status_code == 409 and "v2 went live" in r.json()["detail"]
    rebased = (await client.get(f"/api/workflow/versions/{b}/rebased")).json()
    assert rebased["based_on"] == a
    assert "rank" not in rebased["config"]["steps"]
    assert rebased["config"]["settings"]["gather"]["priors_lookback_days"] == 90
    assert rebased["conflicts"] == [] and rebased["errors"] == []


async def test_only_a_draft_can_be_rebased(client):
    assert (await client.get("/api/workflow/versions/1/rebased")).status_code == 409


async def test_a_version_shows_its_changes_against_the_active_one(client):
    number = (await _draft(client)).json()["number"]
    body = (await client.get(f"/api/workflow/versions/{number}")).json()
    assert body["active_number"] == 1
    assert body["diff"] == [{"path": "settings.gather.priors_lookback_days",
                             "kind": "changed", "before": 180, "after": 90}]


async def test_a_rejection_needs_a_reason(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/reject", json={"reason": ""},
                          headers=ASHA)
    assert r.status_code == 422


async def test_a_rejection_is_recorded(client):
    number = (await _draft(client)).json()["number"]
    r = await client.post(f"/api/workflow/versions/{number}/reject",
                          json={"reason": "too aggressive"}, headers=ASHA)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["reject_reason"]) == ("rejected", "too aggressive")


async def test_an_unknown_version_is_a_404(client):
    assert (await client.get("/api/workflow/versions/99")).status_code == 404


async def test_the_yaml_download_round_trips_through_upload(client):
    r = await client.get("/api/workflow/versions/1/yaml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/yaml")
    assert 'filename="fobo-investigation-v1.yaml"' in r.headers["content-disposition"]
    up = await client.post("/api/workflow/drafts/yaml", json={"yaml": r.text, "note": "re-upload"})
    assert up.status_code == 201 and up.json()["based_on"] == 1
    assert (await client.get(f"/api/workflow/versions/{up.json()['number']}")).json()["diff"] == []


async def test_unreadable_yaml_names_the_line(client):
    r = await client.post("/api/workflow/drafts/yaml",
                          json={"yaml": "steps: [resolve,\n  gather\nname: x: y\n", "note": "bad"})
    assert r.status_code == 422
    assert r.json()["detail"]["errors"][0].startswith("line ")
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_api.py -q`
Expected: FAIL — 404s on `/api/workflow`.

- [ ] **Step 3: Implement the router**

Create `apps/api/api/routes/workflow.py`:

```python
"""The Workflow tab: see the graph, draft a change, approve it as a second person.

Every rule is enforced in app/workflow/versions.py; this module only maps
HTTP onto it. Errors raised there become responses through the VersionError
handler in api/main.py.
"""

import os

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field

from api.auth import current_caller, dev_callers
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import REASONERS, dump_config, settings_schema
from app.workflow.diff import diff, rebase
from app.workflow.registry import catalogue
from app.workflow.yaml_io import YamlError, parse_yaml, to_yaml

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class ConfigBody(BaseModel):
    config: dict


class DraftBody(BaseModel):
    config: dict
    note: str = ""
    based_on: int


class YamlBody(BaseModel):
    yaml: str = Field(max_length=70_000)
    note: str = ""


class RejectBody(BaseModel):
    reason: str = ""


def _overrides() -> dict:
    env = os.getenv("FOBO_REASONER", "").strip().lower()
    return {"reasoner": env} if env else {}


def _caller_view() -> dict:
    c = current_caller()
    return {"id": c.staff_id, "roles": list(c.roles)}


@router.get("")
async def overview() -> dict:
    async with get_session() as s:
        cur = await versions.active(s)
        body = {
            "active": versions.view(await versions.get(s, cur.number)),
            "steps": catalogue(),
            "settings_schema": settings_schema(),
            "reasoners": list(REASONERS),
            "overrides": _overrides(),
            "pending_drafts": await versions.pending_count(s),
            "caller": _caller_view(),
        }
    callers = dev_callers()
    if callers:
        body["dev_callers"] = callers
    return body


@router.get("/versions")
async def history() -> list[dict]:
    async with get_session() as s:
        return [versions.view(r, with_config=False) for r in await versions.list_versions(s)]


@router.get("/versions/{number}")
async def one(number: int) -> dict:
    async with get_session() as s:
        row = await versions.get(s, number)
        cur = await versions.active(s)
        body = versions.view(row)
    changes = diff(dump_config(cur.config), body["config"])
    return body | {"active_number": cur.number, "diff": [c.as_dict() for c in changes]}


@router.get("/versions/{number}/yaml")
async def as_yaml(number: int) -> Response:
    async with get_session() as s:
        row = await versions.get(s, number)
    return Response(
        to_yaml(row), media_type="text/yaml",
        headers={"Content-Disposition":
                 f'attachment; filename="fobo-investigation-v{number}.yaml"'},
    )


@router.get("/versions/{number}/rebased")
async def rebased(number: int) -> dict:
    async with get_session() as s:
        row = await versions.get(s, number)
        if row.status != "draft" or row.based_on is None:
            raise versions.Conflict(f"v{number} is {row.status}; only a draft can be redrafted")
        base = dump_config(versions.as_config((await versions.get(s, row.based_on)).config))
        cur = await versions.active(s)
    merged, conflicts = rebase(base, dump_config(versions.as_config(row.config)),
                               dump_config(cur.config))
    return {"config": merged, "based_on": cur.number, "conflicts": conflicts,
            "errors": versions.validation_errors(merged)}


@router.post("/validate")
async def check(body: ConfigBody) -> dict:
    errors = versions.validation_errors(body.config)
    return {"ok": not errors, "errors": errors}


@router.post("/drafts", status_code=201)
async def draft(body: DraftBody) -> dict:
    async with get_session() as s:
        row = await versions.create_draft(
            s, raw=body.config, note=body.note, based_on=body.based_on, caller=current_caller())
        return versions.view(row)


@router.post("/drafts/yaml", status_code=201)
async def draft_from_yaml(body: YamlBody) -> dict:
    try:
        raw = parse_yaml(body.yaml)
    except YamlError as exc:
        raise versions.Invalid("the YAML could not be read", [str(exc)]) from exc
    async with get_session() as s:
        cur = await versions.active(s)
        row = await versions.create_draft(
            s, raw=raw, note=body.note, based_on=cur.number, caller=current_caller())
        return versions.view(row)


@router.post("/versions/{number}/approve")
async def approve(number: int, idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    async with get_session() as s:
        row = await versions.approve(s, number, caller=current_caller(), key=idempotency_key)
        return versions.view(row)


@router.post("/versions/{number}/reject")
async def reject(number: int, body: RejectBody) -> dict:
    async with get_session() as s:
        row = await versions.reject(s, number, caller=current_caller(), reason=body.reason)
        return versions.view(row)
```

- [ ] **Step 4: Wire it into the app**

In `apps/api/api/main.py`: add `workflow` to the `from api.routes import (...)` list; add imports `from fastapi.responses import JSONResponse` and `from app.workflow.versions import Invalid, VersionError`; add this function above `create_app`:

```python
async def _version_error(_request, exc: VersionError) -> JSONResponse:
    """A refused workflow change, in the API's usual `detail` envelope. A
    validation failure lists every problem so the console can show each one."""
    detail = (
        {"message": str(exc), "errors": exc.errors}
        if isinstance(exc, Invalid) and exc.errors
        else str(exc)
    )
    return JSONResponse(status_code=exc.status, content={"detail": detail})
```

and inside `create_app()`, after the CORS middleware: `app.add_exception_handler(VersionError, _version_error)`; with the other routers: `app.include_router(workflow.router)`.

- [ ] **Step 5: Run the tests**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_workflow_api.py -q` → PASS. Full suite → all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/api/routes/workflow.py apps/api/api/main.py apps/api/tests/test_workflow_api.py
git commit -m "feat: /api/workflow — catalogue, versions, diff, rebase, validate, YAML, approve

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Console API client — dev caller, structured errors, workflow calls

**Files:**
- Modify: `apps/console/src/lib/apiClient.js`
- Create: `apps/console/src/components/helix/data/workflowApi.js`
- Test: `apps/console/src/lib/apiClient.test.js`, `apps/console/src/components/helix/data/workflowApi.test.js`

**Interfaces:**
- Produces: `apiClient` exports `get(path)`, `getText(path)`, `post(path, body, extraHeaders)`, `ApiError` (`message`, `status`, `errors: string[]`), `DEV_CALLER_KEY = 'fobo.devCaller'`, `devCaller(): string|null`, `setDevCaller(id|null)`, `API_BASE`. `workflowApi` exports `fetchWorkflow()`, `fetchVersions()`, `fetchVersion(n)`, `fetchRebased(n)`, `validateWorkflow(config)`, `saveDraft({config, note, basedOn})`, `uploadYaml({yaml, note})`, `approveVersion(n, key)`, `rejectVersion(n, reason)`, `downloadYaml(n)`.

- [ ] **Step 1: Write the failing tests**

Create `apps/console/src/lib/apiClient.test.js`:

```js
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, DEV_CALLER_KEY, get, post, setDevCaller } from './apiClient';

const reply = (status, body) => ({
  ok: status < 400,
  status,
  json: async () => {
    if (body === undefined) throw new Error('no body');
    return body;
  },
  text: async () => JSON.stringify(body),
});

beforeEach(() => {
  global.fetch = vi.fn();
  setDevCaller(null);
});

afterEach(() => vi.restoreAllMocks());

describe('apiClient', () => {
  it('sends no identity header by default', async () => {
    fetch.mockResolvedValue(reply(200, {}));
    await get('/x');
    expect(fetch.mock.calls[0][1].headers).toEqual({});
  });

  it('sends X-Dev-Caller once a dev caller is chosen', async () => {
    setDevCaller('asha');
    fetch.mockResolvedValue(reply(200, {}));
    await post('/x', { a: 1 });
    expect(fetch.mock.calls[0][1].headers['X-Dev-Caller']).toBe('asha');
  });

  it('remembers the choice across reloads', () => {
    setDevCaller('asha');
    expect(window.localStorage.getItem(DEV_CALLER_KEY)).toBe('asha');
  });

  it('still switches when browser storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    setDevCaller('asha');
    fetch.mockResolvedValue(reply(200, {}));
    await get('/x');
    expect(fetch.mock.calls[0][1].headers['X-Dev-Caller']).toBe('asha');
  });

  it('surfaces every problem the server listed', async () => {
    fetch.mockResolvedValue(
      reply(422, { detail: { message: 'workflow is invalid', errors: ['a', 'b'] } }),
    );
    const err = await post('/x', {}).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect([err.message, err.status, err.errors]).toEqual(['workflow is invalid', 422, ['a', 'b']]);
  });

  it('keeps a plain detail as the message', async () => {
    fetch.mockResolvedValue(reply(403, { detail: 'a second Product Control user must approve' }));
    const err = await post('/x', {}).catch((e) => e);
    expect(err.message).toBe('a second Product Control user must approve');
    expect(err.errors).toEqual([]);
  });

  it('turns request validation errors into readable lines', async () => {
    fetch.mockResolvedValue(reply(422, { detail: [{ loc: ['body', 'note'], msg: 'Field required' }] }));
    const err = await post('/x', {}).catch((e) => e);
    expect(err.message).toBe('note: Field required');
  });

  it('falls back to the method, path and status', async () => {
    fetch.mockResolvedValue(reply(500));
    const err = await get('/x').catch((e) => e);
    expect(err.message).toBe('GET /x failed: 500');
  });
});
```

Create `apps/console/src/components/helix/data/workflowApi.test.js`:

```js
import { beforeEach, expect, it, vi } from 'vitest';
import * as client from '@/lib/apiClient';
import { approveVersion, saveDraft, uploadYaml } from './workflowApi';

vi.mock('@/lib/apiClient', () => ({
  API_BASE: 'http://api',
  get: vi.fn(),
  getText: vi.fn(),
  post: vi.fn(),
}));

beforeEach(() => vi.clearAllMocks());

it('saves a draft with the API field names', async () => {
  await saveDraft({ config: { steps: [] }, note: 'why', basedOn: 3 });
  expect(client.post).toHaveBeenCalledWith('/api/workflow/drafts', {
    config: { steps: [] },
    note: 'why',
    based_on: 3,
  });
});

it('approves with the idempotency key the dialog chose', async () => {
  await approveVersion(5, 'key-1');
  expect(client.post).toHaveBeenCalledWith('/api/workflow/versions/5/approve', null, {
    'Idempotency-Key': 'key-1',
  });
});

it('uploads YAML text with its note', async () => {
  await uploadYaml({ yaml: 'steps: []', note: 'n' });
  expect(client.post).toHaveBeenCalledWith('/api/workflow/drafts/yaml', { yaml: 'steps: []', note: 'n' });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/console && npx vitest run src/lib/apiClient.test.js src/components/helix/data/workflowApi.test.js`
Expected: FAIL — `ApiError` / `setDevCaller` not exported; `workflowApi` missing.

- [ ] **Step 3: Implement the client**

Replace `apps/console/src/lib/apiClient.js` with:

```js
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8100';

// Dev only: act as another caller, so a workflow change drafted by one
// person can be approved by another. The API ignores the header unless it
// runs with FOBO_ENV=dev.
export const DEV_CALLER_KEY = 'fobo.devCaller';
let memoryCaller = null;

export function devCaller() {
  try {
    return window.localStorage.getItem(DEV_CALLER_KEY) || memoryCaller;
  } catch {
    return memoryCaller;
  }
}

export function setDevCaller(id) {
  memoryCaller = id || null;
  try {
    if (id) window.localStorage.setItem(DEV_CALLER_KEY, id);
    else window.localStorage.removeItem(DEV_CALLER_KEY);
  } catch {
    // Storage blocked (a private window): the choice lasts until reload.
  }
}

const identity = () => {
  const id = devCaller();
  return id ? { 'X-Dev-Caller': id } : {};
};

/** A failed call, in the server's own words; for a refused workflow change,
 * every problem it listed. */
export class ApiError extends Error {
  constructor(message, { status, errors = [] } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errors = errors;
  }
}

const requestErrors = (detail) =>
  detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`);

async function failure(res, method, path) {
  let detail = '';
  try {
    detail = (await res.json())?.detail ?? '';
  } catch {
    detail = '';
  }
  const fallback = `${method} ${path} failed: ${res.status}`;
  if (Array.isArray(detail)) {
    const errors = requestErrors(detail);
    return new ApiError(errors.join('; ') || fallback, { status: res.status, errors });
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(detail.message || fallback, {
      status: res.status,
      errors: detail.errors || [],
    });
  }
  // Surface the server's own explanation: "a rejection requires a reason"
  // is far more useful than "422".
  return new ApiError(detail || fallback, { status: res.status });
}

async function fetchOk(method, path, init) {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw await failure(res, method, path);
  return res;
}

export async function get(path) {
  const res = await fetchOk('GET', path, { cache: 'no-store', headers: identity() });
  return res.json();
}

export async function getText(path) {
  const res = await fetchOk('GET', path, { cache: 'no-store', headers: identity() });
  return res.text();
}

export async function post(path, body, extraHeaders = {}) {
  const res = await fetchOk('POST', path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...identity(), ...extraHeaders },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.status === 202 || res.status === 204 ? null : res.json();
}
```

- [ ] **Step 4: Implement the workflow calls**

Create `apps/console/src/components/helix/data/workflowApi.js`:

```js
import { get, getText, post } from '@/lib/apiClient';

/** Every call the Workflow tab makes to the orchestrator. */

export const fetchWorkflow = () => get('/api/workflow');

export const fetchVersions = () => get('/api/workflow/versions');

export const fetchVersion = (n) => get(`/api/workflow/versions/${n}`);

export const fetchRebased = (n) => get(`/api/workflow/versions/${n}/rebased`);

export const validateWorkflow = (config) => post('/api/workflow/validate', { config });

export const saveDraft = ({ config, note, basedOn }) =>
  post('/api/workflow/drafts', { config, note, based_on: basedOn });

export const uploadYaml = ({ yaml, note }) => post('/api/workflow/drafts/yaml', { yaml, note });

/** The key is chosen once per confirmation, so a retry of the same click can
 * never approve twice; the API refuses a repeated key. */
export const approveVersion = (n, key) =>
  post(`/api/workflow/versions/${n}/approve`, null, { 'Idempotency-Key': key });

export const rejectVersion = (n, reason) => post(`/api/workflow/versions/${n}/reject`, { reason });

export async function downloadYaml(n) {
  const text = await getText(`/api/workflow/versions/${n}/yaml`);
  const url = URL.createObjectURL(new Blob([text], { type: 'text/yaml' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `fobo-investigation-v${n}.yaml`;
  a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 5: Run the tests**

Run: `cd apps/console && npx vitest run` → all pass (55 existing + new).

- [ ] **Step 6: Commit**

```bash
git add apps/console/src/lib apps/console/src/components/helix/data/workflowApi.js apps/console/src/components/helix/data/workflowApi.test.js
git commit -m "feat: console API client sends the dev caller and keeps structured errors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Workflow graph (view mode) and step panel

**Files:**
- Create: `apps/console/src/components/helix/workflow/__fixtures__/workflow.json` (generated)
- Create: `apps/console/src/components/helix/workflow/workflowModel.js`
- Create: `apps/console/src/components/helix/workflow/StepCard.jsx`
- Create: `apps/console/src/components/helix/workflow/WorkflowGraph.jsx`
- Create: `apps/console/src/components/helix/workflow/StepPanel.jsx`
- Test: `workflowModel.test.js`, `WorkflowGraph.test.jsx`, `StepPanel.test.jsx` in the same folder

**Interfaces:**
- Consumes: `Drawer` (`../ui/Drawer`), `mono`, `manrope` (`../lib/format`).
- Produces:
  - `workflowModel.js`: `TAG_STYLE` (tones `grey|green|purple|blue|amber|red` → `{bg, fg}`), `STATUS_TONE`, `decidedByChips(decidedBy, reasoner) -> {label, tone}[]`, `effectiveReasoner(config, overrides)`, `byName(catalogue)`, `errorsFor(errors, name)`, `moveStep(config, index, delta)`, `removeStep(config, name)`, `addStep(config, name, catalogue)`, `togglePause(config, name)`, `setSetting(config, section, key, value)`, `excludedSteps(config, catalogue)`, `SETTINGS_FOR_STEP`, `describeChange(change)`, `humanize(key)`, `showValue(v)`, `when(iso)`.
  - `<StepCard step index total reasoner errors editing onSelect onMove onRemove />`
  - `<WorkflowGraph config catalogue reasoner errors editing onSelect onChange />` — `onChange(nextConfig)` in edit mode.
  - `<StepPanel step config schema reasoner onClose />`

- [ ] **Step 1: Generate the fixture from the real code**

Run from the repo root:

```bash
mkdir -p apps/console/src/components/helix/workflow/__fixtures__
cd apps/api && .venv/bin/python - <<'EOF' > ../console/src/components/helix/workflow/__fixtures__/workflow.json
import json
from app.workflow.config import REASONERS, dump_config, read_workflow, settings_schema
from app.workflow.registry import catalogue
print(json.dumps({
    "active": {
        "number": 3, "status": "active", "note": "Lookback 180→90 days", "based_on": 2,
        "drafted_by": "praveen", "drafted_at": "2026-09-24T14:02:00+00:00",
        "decided_by": "asha", "decided_at": "2026-09-24T14:10:00+00:00",
        "reject_reason": None, "config": dump_config(read_workflow()),
    },
    "steps": catalogue(),
    "settings_schema": settings_schema(),
    "reasoners": list(REASONERS),
    "overrides": {},
    "pending_drafts": 2,
    "caller": {"id": "praveen", "roles": ["FO", "PC"]},
    "dev_callers": [{"id": "praveen", "roles": ["FO", "PC"]}, {"id": "asha", "roles": ["PC"]}],
}, indent=2, ensure_ascii=False))
EOF
```

Expected: a JSON file whose `steps` has 9 entries and whose `active.config.steps` starts with `resolve`.

- [ ] **Step 2: Write the failing tests**

Create `apps/console/src/components/helix/workflow/workflowModel.test.js`:

```js
import { describe, expect, it } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import {
  addStep,
  decidedByChips,
  describeChange,
  effectiveReasoner,
  errorsFor,
  excludedSteps,
  moveStep,
  removeStep,
  setSetting,
  togglePause,
} from './workflowModel';

const config = () => structuredClone(fixture.active.config);

describe('workflowModel', () => {
  it('tags the playbook step with the reasoner in force', () => {
    expect(decidedByChips('playbook+reasoner', 'none')).toEqual([
      { label: 'Playbook', tone: 'green' },
      { label: 'Reasoner: none', tone: 'purple' },
    ]);
    expect(decidedByChips('human')).toEqual([{ label: 'Human', tone: 'blue' }]);
    expect(decidedByChips('code')).toEqual([{ label: 'Code', tone: 'grey' }]);
  });

  it('prefers an environment override to the configured reasoner', () => {
    expect(effectiveReasoner(config(), {})).toBe('none');
    expect(effectiveReasoner(config(), { reasoner: 'direct' })).toBe('direct');
  });

  it('moves a step without touching the original', () => {
    const before = config();
    const after = moveStep(before, 4, 1);
    expect(after.steps.slice(4, 6)).toEqual(['draft', 'rank']);
    expect(before.steps[4]).toBe('rank');
    expect(moveStep(before, 0, -1)).toBe(before);
  });

  it('removing a step also removes its pause', () => {
    const paused = togglePause(config(), 'rank');
    expect(removeStep(paused, 'rank').pause_before).toEqual(['review']);
  });

  it('adds a step back where the registry puts it', () => {
    const without = removeStep(config(), 'rank');
    expect(addStep(without, 'rank', fixture.steps).steps).toEqual(config().steps);
    expect(excludedSteps(without, fixture.steps).map((s) => s.name)).toEqual(['rank']);
  });

  it('sets a setting immutably', () => {
    const before = config();
    const after = setSetting(before, 'gather', 'priors_lookback_days', 90);
    expect(after.settings.gather.priors_lookback_days).toBe(90);
    expect(before.settings.gather.priors_lookback_days).toBe(180);
  });

  it('finds the errors that name a step', () => {
    const errors = ["steps: 'draft' needs 'pattern_groups' before it runs", 'other'];
    expect(errorsFor(errors, 'draft')).toEqual([errors[0]]);
  });

  it('reads each kind of change as a sentence', () => {
    expect(describeChange({ path: 'steps.rank', kind: 'removed', before: 4 })).toBe(
      'rank removed (was step 5)',
    );
    expect(describeChange({ path: 'steps.rank', kind: 'added', after: 4 })).toBe(
      'rank added as step 5',
    );
    expect(describeChange({ path: 'steps.rank', kind: 'moved', before: 4, after: 6 })).toBe(
      'rank moved from step 5 to step 7',
    );
    expect(describeChange({ path: 'pause_before.reason', kind: 'added' })).toBe(
      'pause added before reason',
    );
    expect(
      describeChange({
        path: 'settings.gather.priors_lookback_days',
        kind: 'changed',
        before: 180,
        after: 90,
      }),
    ).toBe('gather.priors_lookback_days: 180 → 90');
  });
});
```

Create `apps/console/src/components/helix/workflow/WorkflowGraph.test.jsx`:

```jsx
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import { WorkflowGraph } from './WorkflowGraph';

const renderGraph = (props = {}) => {
  const handlers = { onSelect: vi.fn(), onChange: vi.fn() };
  render(
    <WorkflowGraph
      config={fixture.active.config}
      catalogue={fixture.steps}
      reasoner="none"
      {...handlers}
      {...props}
    />,
  );
  return handlers;
};

const card = (name) =>
  screen.getAllByTestId('step-card').find((c) => c.dataset.step === name);

describe('WorkflowGraph', () => {
  it('draws the configured steps in order', () => {
    renderGraph();
    expect(screen.getAllByTestId('step-card').map((c) => c.dataset.step)).toEqual(
      fixture.active.config.steps,
    );
  });

  it('tags each step with who decides it', () => {
    renderGraph();
    expect(within(card('reason')).getByText('Playbook')).toBeInTheDocument();
    expect(within(card('reason')).getByText('Reasoner: none')).toBeInTheDocument();
    expect(within(card('review')).getByText('Human')).toBeInTheDocument();
  });

  it('marks locked steps and says why', () => {
    renderGraph();
    expect(within(card('validate')).getByLabelText(/Cannot be removed/)).toBeInTheDocument();
    expect(within(card('rank')).queryByLabelText(/Cannot be removed/)).toBeNull();
  });

  it('shows where the run pauses and which steps can escalate', () => {
    renderGraph();
    expect(screen.getByLabelText('Pauses before review')).toBeInTheDocument();
    const escalate = screen.getByTestId('escalate');
    expect(within(escalate).getByText(/Resolve books/)).toBeInTheDocument();
    expect(within(escalate).getByText(/Gather evidence/)).toBeInTheDocument();
  });

  it('opens a step when its card is clicked', async () => {
    const { onSelect } = renderGraph();
    await userEvent.click(screen.getByRole('button', { name: 'Open Apply playbook' }));
    expect(onSelect).toHaveBeenCalledWith('reason');
  });

  it('in edit mode, toggles a pause, removes and moves steps', async () => {
    const { onChange } = renderGraph({ editing: true });
    await userEvent.click(screen.getByRole('button', { name: 'Pause before reason' }));
    expect(onChange.mock.lastCall[0].pause_before).toEqual(['review', 'reason']);
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    expect(onChange.mock.lastCall[0].steps).not.toContain('rank');
    await userEvent.click(screen.getByRole('button', { name: 'Move rank earlier' }));
    expect(onChange.mock.lastCall[0].steps.slice(3, 5)).toEqual(['rank', 'reason']);
  });

  it('shows a validation error on the step it names', () => {
    renderGraph({ errors: ["steps: 'draft' needs 'pattern_groups' before it runs"] });
    expect(within(card('draft')).getByRole('alert')).toHaveTextContent('pattern_groups');
  });

  it('draws an unknown step instead of failing', () => {
    const config = { ...fixture.active.config, steps: [...fixture.active.config.steps, 'mystery'] };
    renderGraph({ config });
    expect(within(card('mystery')).getByText('Not a known step')).toBeInTheDocument();
  });
});
```

Create `apps/console/src/components/helix/workflow/StepPanel.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import { StepPanel } from './StepPanel';

const step = (name) => fixture.steps.find((s) => s.name === name);
const renderPanel = (name) =>
  render(
    <StepPanel
      step={step(name)}
      config={fixture.active.config}
      schema={fixture.settings_schema}
      reasoner="none"
      onClose={vi.fn()}
    />,
  );

it('shows a step’s settings with their meaning', () => {
  renderPanel('gather');
  expect(screen.getByText('priors lookback days')).toBeInTheDocument();
  expect(screen.getByText('180')).toBeInTheDocument();
  expect(screen.getByText(/How far back to look/)).toBeInTheDocument();
});

it('shows the session service settings with the playbook step', () => {
  renderPanel('reason');
  expect(screen.getByText('timeout seconds')).toBeInTheDocument();
});

it('says why a locked step cannot be removed', () => {
  renderPanel('review');
  expect(screen.getByText("Why it can't be removed")).toBeInTheDocument();
  expect(screen.getByText(/no decision is recorded without a person/)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd apps/console && npx vitest run src/components/helix/workflow`
Expected: FAIL — modules not found.

- [ ] **Step 4: Implement the model helpers**

Create `apps/console/src/components/helix/workflow/workflowModel.js`:

```js
/** Pure helpers for the Workflow tab. Nothing here changes its inputs. */

export const TAG_STYLE = {
  grey: { bg: 'var(--bg-muted)', fg: 'var(--text-secondary)' },
  green: { bg: 'var(--clr-green-bg)', fg: 'var(--clr-green)' },
  purple: { bg: 'var(--clr-purple-bg)', fg: 'var(--clr-purple)' },
  blue: { bg: 'var(--clr-blue-bg)', fg: 'var(--clr-blue)' },
  amber: { bg: 'var(--clr-amber-bg)', fg: 'var(--clr-amber)' },
  red: { bg: 'var(--clr-red-bg)', fg: 'var(--clr-red)' },
};

export const STATUS_TONE = { active: 'green', draft: 'amber', superseded: 'grey', rejected: 'red' };

/** The chips that say who decides a step, from the registry's decided_by. */
export function decidedByChips(decidedBy, reasoner) {
  switch (decidedBy) {
    case 'playbook+reasoner':
      return [
        { label: 'Playbook', tone: 'green' },
        { label: `Reasoner: ${reasoner}`, tone: 'purple' },
      ];
    case 'code+model':
      return [
        { label: 'Code', tone: 'grey' },
        { label: 'Multi-cause: model (not built)', tone: 'grey' },
      ];
    case 'template':
      return [{ label: 'Template · model planned', tone: 'grey' }];
    case 'human':
      return [{ label: 'Human', tone: 'blue' }];
    default:
      return [{ label: 'Code', tone: 'grey' }];
  }
}

/** The reasoner actually in force: an environment override beats the config. */
export const effectiveReasoner = (config, overrides) =>
  overrides?.reasoner || config.settings.reason.reasoner;

export const byName = (catalogue) => Object.fromEntries(catalogue.map((s) => [s.name, s]));

/** Errors that name this step, e.g. "steps: 'draft' needs 'pattern_groups'". */
export const errorsFor = (errors, name) => errors.filter((e) => e.includes(`'${name}'`));

export function moveStep(config, index, delta) {
  const to = index + delta;
  if (to < 0 || to >= config.steps.length) return config;
  const steps = [...config.steps];
  [steps[index], steps[to]] = [steps[to], steps[index]];
  return { ...config, steps };
}

export const removeStep = (config, name) => ({
  ...config,
  steps: config.steps.filter((s) => s !== name),
  pause_before: config.pause_before.filter((s) => s !== name),
});

/** Put a step back where the registry places it among the steps present. */
export function addStep(config, name, catalogue) {
  const order = catalogue.map((s) => s.name);
  const at = config.steps.findIndex((s) => order.indexOf(s) > order.indexOf(name));
  const steps =
    at === -1
      ? [...config.steps, name]
      : [...config.steps.slice(0, at), name, ...config.steps.slice(at)];
  return { ...config, steps };
}

export const togglePause = (config, name) => ({
  ...config,
  pause_before: config.pause_before.includes(name)
    ? config.pause_before.filter((s) => s !== name)
    : [...config.pause_before, name],
});

export const setSetting = (config, section, key, value) => ({
  ...config,
  settings: { ...config.settings, [section]: { ...config.settings[section], [key]: value } },
});

export const excludedSteps = (config, catalogue) =>
  catalogue.filter((s) => s.removable && !config.steps.includes(s.name));

/** Settings sections shown with each step; the session service serves the reasoner. */
export const SETTINGS_FOR_STEP = {
  gather: ['gather'],
  reason: ['reason', 'session_service'],
  validate: ['validate'],
  review: ['review'],
};

export const humanize = (key) => key.replace(/_/g, ' ');

export const showValue = (v) => {
  if (Array.isArray(v)) return v.length ? v.join(', ') : '(none)';
  if (v === null || v === undefined || v === '') return '(unset)';
  return String(v);
};

const stepNo = (i) => `step ${i + 1}`;

/** One diff entry from the API, as a line a controller can read. */
export function describeChange({ path, kind, before, after }) {
  const [head, ...rest] = path.split('.');
  const name = rest.join('.');
  if (head === 'steps') {
    if (kind === 'removed') return `${name} removed (was ${stepNo(before)})`;
    if (kind === 'added') return `${name} added as ${stepNo(after)}`;
    return `${name} moved from ${stepNo(before)} to ${stepNo(after)}`;
  }
  if (head === 'pause_before') {
    return `pause ${kind === 'added' ? 'added' : 'removed'} before ${name}`;
  }
  const label = head === 'settings' ? name : path;
  return `${label}: ${showValue(before)} → ${showValue(after)}`;
}

export const when = (iso) =>
  iso
    ? new Date(iso).toLocaleString('en-GB', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC',
      })
    : '';
```

- [ ] **Step 5: Implement the card**

Create `apps/console/src/components/helix/workflow/StepCard.jsx`:

```jsx
import { ChevronLeft, ChevronRight, CornerDownRight, Lock, Minus } from 'lucide-react';
import { mono } from '../lib/format';
import { TAG_STYLE, decidedByChips } from './workflowModel';

function IconButton({ label, disabled, onClick, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="p-1 rounded disabled:opacity-30 hover:opacity-80"
      style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
    >
      {children}
    </button>
  );
}

export function Chip({ label, tone }) {
  const t = TAG_STYLE[tone] || TAG_STYLE.grey;
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-semibold whitespace-nowrap"
      style={{ background: t.bg, color: t.fg }}
    >
      {label}
    </span>
  );
}

export function StepCard({
  step,
  index,
  total,
  reasoner,
  errors = [],
  editing = false,
  onSelect,
  onMove,
  onRemove,
}) {
  return (
    <div
      data-testid="step-card"
      data-step={step.name}
      className="rounded-xl px-3 py-2.5 flex flex-col gap-1.5 w-full md:w-[172px]"
      style={{
        background: 'var(--bg-card-solid)',
        border: `1px solid ${errors.length ? 'var(--clr-red)' : 'var(--border)'}`,
        boxShadow: 'var(--card-shadow)',
      }}
    >
      <button
        type="button"
        onClick={() => onSelect(step.name)}
        className="text-left"
        aria-label={`Open ${step.label}`}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] tabular-nums" style={{ color: 'var(--text-muted)' }}>
            {index + 1}
          </span>
          <span
            className="text-[13px] font-semibold truncate"
            style={{ color: 'var(--text-primary)' }}
          >
            {step.label}
          </span>
          {!step.removable && (
            <span
              role="img"
              aria-label={`Cannot be removed: ${step.required_because}`}
              title={`Cannot be removed: ${step.required_because}`}
              style={{ color: 'var(--text-muted)' }}
            >
              <Lock size={11} />
            </span>
          )}
        </div>
        <div className="text-[10px]" style={{ ...mono, color: 'var(--text-muted)' }}>
          {step.name}
        </div>
      </button>
      <div className="flex flex-wrap gap-1">
        {decidedByChips(step.decided_by, reasoner).map((c) => (
          <Chip key={c.label} {...c} />
        ))}
      </div>
      {step.unknown && (
        <div className="text-[10.5px]" style={{ color: 'var(--clr-red)' }}>
          Not a known step
        </div>
      )}
      {step.can_escalate && (
        <div className="text-[10px] flex items-center gap-1" style={{ color: 'var(--clr-red)' }}>
          <CornerDownRight size={10} /> can escalate → end
        </div>
      )}
      {errors.map((e) => (
        <div key={e} role="alert" className="text-[10.5px]" style={{ color: 'var(--clr-red)' }}>
          {e}
        </div>
      ))}
      {editing && (
        <div className="flex gap-1 pt-1.5" style={{ borderTop: '1px solid var(--border)' }}>
          <IconButton
            label={`Move ${step.name} earlier`}
            disabled={index === 0}
            onClick={() => onMove(index, -1)}
          >
            <ChevronLeft size={12} />
          </IconButton>
          <IconButton
            label={`Move ${step.name} later`}
            disabled={index === total - 1}
            onClick={() => onMove(index, 1)}
          >
            <ChevronRight size={12} />
          </IconButton>
          {step.removable && (
            <IconButton label={`Remove ${step.name}`} onClick={() => onRemove(step.name)}>
              <Minus size={12} />
            </IconButton>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Implement the graph**

Create `apps/console/src/components/helix/workflow/WorkflowGraph.jsx`:

```jsx
import { ArrowRight, CirclePause } from 'lucide-react';
import { StepCard } from './StepCard';
import { byName, errorsFor, moveStep, removeStep, togglePause } from './workflowModel';

const unknownStep = (name) => ({
  name,
  unknown: true,
  label: name,
  description: 'Not a known step',
  decided_by: 'code',
  removable: true,
  required_because: null,
  can_escalate: false,
  needs: [],
  produces: [],
  must_follow: [],
});

function Gap({ name, first, paused, editing, onToggle }) {
  const marker = (
    <span
      className="flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded"
      style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
    >
      <CirclePause size={10} /> Pause
    </span>
  );
  return (
    <div className="flex md:flex-col items-center justify-center gap-1 px-1 py-1 md:py-0">
      {!first && (
        <ArrowRight
          size={14}
          className="rotate-90 md:rotate-0"
          style={{ color: 'var(--text-muted)' }}
        />
      )}
      {editing ? (
        <button
          type="button"
          aria-label={`${paused ? 'Remove pause' : 'Pause'} before ${name}`}
          aria-pressed={paused}
          onClick={onToggle}
          className="rounded px-1 py-0.5 text-[10px]"
          style={{ border: '1px dashed var(--border)', color: 'var(--text-muted)' }}
        >
          {paused ? marker : '+ pause'}
        </button>
      ) : (
        paused && <span aria-label={`Pauses before ${name}`}>{marker}</span>
      )}
    </div>
  );
}

function EscalateCard({ sources }) {
  return (
    <div
      data-testid="escalate"
      className="rounded-xl px-3 py-2.5 w-full md:w-[150px] text-[11px]"
      style={{ border: '1px dashed var(--clr-red)', color: 'var(--clr-red)' }}
    >
      <div className="font-semibold">Escalate → end</div>
      <div style={{ color: 'var(--text-muted)' }}>from {sources.join(', ') || 'no step'}</div>
    </div>
  );
}

export function WorkflowGraph({
  config,
  catalogue,
  reasoner,
  errors = [],
  editing = false,
  onSelect,
  onChange,
}) {
  const known = byName(catalogue);
  const stepOf = (name) => known[name] || unknownStep(name);
  const escalating = config.steps.filter((n) => stepOf(n).can_escalate).map((n) => stepOf(n).label);
  return (
    <ol
      aria-label="Workflow steps"
      className="flex flex-col md:flex-row md:flex-wrap md:items-center gap-1"
    >
      {config.steps.map((name, i) => (
        <li key={name} className="flex flex-col md:flex-row md:items-center">
          <Gap
            name={name}
            first={i === 0}
            paused={config.pause_before.includes(name)}
            editing={editing}
            onToggle={() => onChange(togglePause(config, name))}
          />
          <StepCard
            step={stepOf(name)}
            index={i}
            total={config.steps.length}
            reasoner={reasoner}
            errors={errorsFor(errors, name)}
            editing={editing}
            onSelect={onSelect}
            onMove={(index, delta) => onChange(moveStep(config, index, delta))}
            onRemove={(n) => onChange(removeStep(config, n))}
          />
        </li>
      ))}
      <li className="md:ml-2 mt-2 md:mt-0">
        <EscalateCard sources={escalating} />
      </li>
    </ol>
  );
}
```

- [ ] **Step 7: Implement the step panel**

Create `apps/console/src/components/helix/workflow/StepPanel.jsx`:

```jsx
import { mono } from '../lib/format';
import { Drawer } from '../ui/Drawer';
import { Chip } from './StepCard';
import { SETTINGS_FOR_STEP, decidedByChips, humanize, showValue } from './workflowModel';

function Section({ title, children }) {
  return (
    <section className="mb-4">
      <h4
        className="text-[11px] font-bold uppercase tracking-wide mb-1.5"
        style={{ color: 'var(--text-muted)' }}
      >
        {title}
      </h4>
      {children}
    </section>
  );
}

function Keys({ keys }) {
  if (!keys.length) return <span className="text-[12px]">(none)</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {keys.map((k) => (
        <span
          key={k}
          className="text-[10.5px] px-1.5 py-0.5 rounded"
          style={{ ...mono, background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}
        >
          {k}
        </span>
      ))}
    </div>
  );
}

export function StepPanel({ step, config, schema, reasoner, onClose }) {
  const sections = SETTINGS_FOR_STEP[step.name] || [];
  return (
    <Drawer title={step.label} subtitle={`${step.name} · ${step.description}`} width={480} onClose={onClose}>
      <Section title="Decided by">
        <div className="flex flex-wrap gap-1">
          {decidedByChips(step.decided_by, reasoner).map((c) => (
            <Chip key={c.label} {...c} />
          ))}
        </div>
      </Section>
      {step.required_because && (
        <Section title="Why it can't be removed">
          <p className="text-[12.5px]" style={{ color: 'var(--text-primary)' }}>
            {step.required_because}
          </p>
        </Section>
      )}
      <Section title="Needs">
        <Keys keys={step.needs} />
      </Section>
      <Section title="Produces">
        <Keys keys={step.produces} />
      </Section>
      {step.must_follow.length > 0 && (
        <Section title="Must come after">
          <Keys keys={step.must_follow} />
        </Section>
      )}
      {sections.map((sec) => (
        <Section key={sec} title={`Settings · ${sec}`}>
          <dl className="flex flex-col gap-2">
            {Object.entries(schema[sec] || {}).map(([key, meta]) => (
              <div key={key}>
                <dt className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {humanize(key)}
                </dt>
                <dd className="text-[12px]" style={{ ...mono, color: 'var(--text-secondary)' }}>
                  {showValue(config.settings[sec]?.[key])}
                </dd>
                <dd className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                  {meta.description}
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      ))}
      {!sections.length && (
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          This step has no settings.
        </p>
      )}
    </Drawer>
  );
}
```

- [ ] **Step 8: Run the tests**

Run: `cd apps/console && npx vitest run` → all pass.

- [ ] **Step 9: Commit**

```bash
git add apps/console/src/components/helix/workflow
git commit -m "feat: workflow graph with who-decides tags, pause points and step panel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Draft editor with live validation

**Files:**
- Create: `apps/console/src/components/helix/workflow/SettingsForm.jsx`
- Create: `apps/console/src/components/helix/workflow/ErrorList.jsx`
- Create: `apps/console/src/components/helix/workflow/DraftEditor.jsx`
- Test: `apps/console/src/components/helix/workflow/DraftEditor.test.jsx`

**Interfaces:**
- Consumes: `validateWorkflow`, `saveDraft` (Task 9); `WorkflowGraph`, `StepPanel`, `workflowModel` helpers (Task 10).
- Produces: `<SettingsForm config schema onChange(section, key, value) />`; `<ErrorList error />` (renders `error.message` and each of `error.errors`); `<DraftEditor initial={{config, basedOn, conflicts}} catalogue schema overrides onSaved(version) onCancel debounceMs=400 />`.

- [ ] **Step 1: Write the failing tests**

Create `apps/console/src/components/helix/workflow/DraftEditor.test.jsx`:

```jsx
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import * as api from '../data/workflowApi';
import fixture from './__fixtures__/workflow.json';
import { DraftEditor } from './DraftEditor';

vi.mock('../data/workflowApi', () => ({
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
}));

const renderEditor = (initial = {}) => {
  const props = { onSaved: vi.fn(), onCancel: vi.fn() };
  render(
    <DraftEditor
      initial={{ config: fixture.active.config, basedOn: 3, conflicts: [], ...initial }}
      catalogue={fixture.steps}
      schema={fixture.settings_schema}
      overrides={{}}
      debounceMs={0}
      {...props}
    />,
  );
  return props;
};

const lastValidated = () => api.validateWorkflow.mock.lastCall[0];
const saveButton = () => screen.getByRole('button', { name: 'Save draft' });

beforeEach(() => {
  vi.clearAllMocks();
  api.validateWorkflow.mockResolvedValue({ ok: true, errors: [] });
});

describe('DraftEditor', () => {
  it('validates the starting config and waits for a note before saving', async () => {
    renderEditor();
    await screen.findByText(/^Valid/);
    expect(saveButton()).toBeDisabled();
  });

  it('checks every edit with the server', async () => {
    renderEditor();
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    await waitFor(() => expect(lastValidated().steps).not.toContain('rank'));
  });

  it('sends a changed setting as a number', async () => {
    renderEditor();
    const input = screen.getByLabelText('priors lookback days');
    await userEvent.clear(input);
    await userEvent.type(input, '90');
    await waitFor(() => expect(lastValidated().settings.gather.priors_lookback_days).toBe(90));
  });

  it('lists the server’s problems, marks the step, and blocks saving', async () => {
    api.validateWorkflow.mockResolvedValue({
      ok: false,
      errors: ["steps: 'draft' needs 'pattern_groups' before it runs — produced by group"],
    });
    renderEditor();
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    const card = await waitFor(() =>
      screen.getAllByTestId('step-card').find((c) => c.dataset.step === 'draft'),
    );
    await waitFor(() => expect(within(card).getByRole('alert')).toBeInTheDocument());
    expect(saveButton()).toBeDisabled();
  });

  it('saves a valid draft with its note and base version', async () => {
    const version = { number: 4, status: 'draft' };
    api.saveDraft.mockResolvedValue(version);
    const { onSaved } = renderEditor();
    await screen.findByText(/^Valid/);
    await userEvent.type(screen.getByLabelText('Change note'), 'Lookback 180→90 days');
    await userEvent.click(saveButton());
    expect(api.saveDraft).toHaveBeenCalledWith({
      config: fixture.active.config,
      note: 'Lookback 180→90 days',
      basedOn: 3,
    });
    expect(onSaved).toHaveBeenCalledWith(version);
  });

  it('shows what the server refused when saving fails', async () => {
    api.saveDraft.mockRejectedValue(
      new ApiError('workflow is invalid', { status: 422, errors: ['first', 'second'] }),
    );
    renderEditor();
    await screen.findByText(/^Valid/);
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    await userEvent.click(saveButton());
    expect(await screen.findByText('second')).toBeInTheDocument();
  });

  it('never enables saving while the check cannot reach the server', async () => {
    api.validateWorkflow.mockRejectedValue(new Error('offline'));
    renderEditor();
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    expect(await screen.findByText(/Couldn't check/)).toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });

  it('lists conflicts carried over from a redraft', () => {
    renderEditor({ conflicts: ['settings.gather.priors_lookback_days'] });
    expect(screen.getByText(/settings.gather.priors_lookback_days/)).toBeInTheDocument();
  });

  it('can put a removed step back', async () => {
    renderEditor();
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    await userEvent.click(screen.getByRole('button', { name: 'Add rank' }));
    await waitFor(() => expect(lastValidated().steps).toEqual(fixture.active.config.steps));
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/console && npx vitest run src/components/helix/workflow/DraftEditor.test.jsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the settings form**

Create `apps/console/src/components/helix/workflow/SettingsForm.jsx`:

```jsx
import { useState } from 'react';
import { humanize } from './workflowModel';

const inputStyle = {
  background: 'var(--bg-muted)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
};
const inputClass = 'w-full text-[12px] rounded-lg px-2 py-1.5 mt-0.5';

// A cleared field is sent as '' so the server says what is wrong with it.
const toNumber = (raw) => (raw === '' ? '' : Number(raw));
const splitList = (raw) =>
  raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

const range = (meta) => {
  const low = meta.min ?? (meta.exclusive_min !== undefined ? `>${meta.exclusive_min}` : null);
  if (low === null && meta.max === undefined) return '';
  return ` (${low ?? ''}–${meta.max ?? ''})`;
};

function ListInput({ id, value, onChange }) {
  const [text, setText] = useState((value || []).join(', '));
  return (
    <input
      id={id}
      type="text"
      className={inputClass}
      style={inputStyle}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        onChange(splitList(e.target.value));
      }}
    />
  );
}

function Field({ id, name, meta, value, onChange }) {
  let input;
  if (meta.type === 'enum') {
    input = (
      <select id={id} className={inputClass} style={inputStyle} value={value} onChange={(e) => onChange(e.target.value)}>
        {meta.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  } else if (meta.type === 'string_list') {
    input = <ListInput id={id} value={value} onChange={onChange} />;
  } else {
    input = (
      <input
        id={id}
        type="number"
        className={inputClass}
        style={inputStyle}
        min={meta.min ?? meta.exclusive_min}
        max={meta.max}
        step={meta.type === 'integer' ? 1 : 'any'}
        value={value ?? ''}
        onChange={(e) => onChange(toNumber(e.target.value))}
      />
    );
  }
  return (
    <div className="mt-2">
      <label htmlFor={id} className="text-[12px] font-semibold" style={{ color: 'var(--text-primary)' }}>
        {humanize(name)}
      </label>
      {input}
      <div className="text-[10.5px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
        {meta.description}
        {range(meta)}
      </div>
    </div>
  );
}

export function SettingsForm({ config, schema, onChange }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {Object.entries(schema).map(([section, fields]) => (
        <fieldset key={section} className="rounded-xl px-3 pb-3" style={{ border: '1px solid var(--border)' }}>
          <legend
            className="text-[11px] font-bold px-1 uppercase tracking-wide"
            style={{ color: 'var(--text-muted)' }}
          >
            {section}
          </legend>
          {Object.entries(fields).map(([key, meta]) => (
            <Field
              key={key}
              id={`setting-${section}-${key}`}
              name={key}
              meta={meta}
              value={config.settings[section]?.[key]}
              onChange={(v) => onChange(section, key, v)}
            />
          ))}
        </fieldset>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Implement the error list**

Create `apps/console/src/components/helix/workflow/ErrorList.jsx`:

```jsx
/** An API failure: the server's message, then every problem it listed. */
export function ErrorList({ error }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="rounded-lg px-3 py-2 text-[12px]"
      style={{ background: 'var(--clr-red-bg)', color: 'var(--clr-red)' }}
    >
      <div className="font-semibold">{error.message}</div>
      {error.errors?.length > 0 && (
        <ul className="list-disc pl-4 mt-1">
          {error.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Implement the editor**

Create `apps/console/src/components/helix/workflow/DraftEditor.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { saveDraft, validateWorkflow } from '../data/workflowApi';
import { ErrorList } from './ErrorList';
import { SettingsForm } from './SettingsForm';
import { StepPanel } from './StepPanel';
import { WorkflowGraph } from './WorkflowGraph';
import {
  addStep,
  byName,
  effectiveReasoner,
  excludedSteps,
  setSetting,
} from './workflowModel';

const RETRY_MS = 3000;

function useServerCheck(config, debounceMs) {
  const [check, setCheck] = useState({ state: 'checking', errors: [] });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    let retry;
    const timer = setTimeout(() => {
      validateWorkflow(config)
        .then((r) => live && setCheck({ state: r.ok ? 'ok' : 'invalid', errors: r.errors }))
        .catch(() => {
          if (!live) return;
          // Keep the last answer; never turn Save on without one.
          setCheck((prev) => ({ ...prev, state: 'offline' }));
          retry = setTimeout(() => setAttempt((a) => a + 1), RETRY_MS);
        });
    }, debounceMs);
    return () => {
      live = false;
      clearTimeout(timer);
      clearTimeout(retry);
    };
  }, [config, attempt, debounceMs]);
  return [check, () => setCheck((prev) => ({ ...prev, state: 'checking' }))];
}

function CheckStatus({ check }) {
  if (check.state === 'checking') return <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>Checking…</p>;
  if (check.state === 'ok')
    return (
      <p className="text-[12px]" style={{ color: 'var(--clr-green)' }}>
        Valid. Once saved, a second Product Control user can approve it.
      </p>
    );
  return (
    <div className="text-[12px]" style={{ color: check.state === 'offline' ? 'var(--clr-amber)' : 'var(--clr-red)' }}>
      {check.state === 'offline' && <p>Couldn't check — retrying.</p>}
      {check.errors.length > 0 && (
        <ul className="list-disc pl-4">
          {check.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DraftEditor({ initial, catalogue, schema, overrides, onSaved, onCancel, debounceMs = 400 }) {
  const [config, setConfig] = useState(initial.config);
  const [note, setNote] = useState('');
  const [save, setSave] = useState({ busy: false, error: null });
  const [open, setOpen] = useState(null);
  const [check, markChecking] = useServerCheck(config, debounceMs);

  const change = (next) => {
    setConfig(next);
    markChecking();
  };
  const canSave = check.state === 'ok' && note.trim().length > 0 && !save.busy;
  const submit = async () => {
    setSave({ busy: true, error: null });
    try {
      onSaved(await saveDraft({ config, note: note.trim(), basedOn: initial.basedOn }));
    } catch (e) {
      setSave({ busy: false, error: e });
    }
  };
  const reasoner = effectiveReasoner(config, overrides);
  const known = byName(catalogue);

  return (
    <section aria-label="Draft editor" className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h3 className="text-[14px] font-bold" style={{ color: 'var(--text-primary)' }}>
          New draft, based on v{initial.basedOn}
        </h3>
        <button type="button" onClick={onCancel} className="ml-auto text-[12px] px-3 py-1 rounded-full" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          Cancel
        </button>
      </div>
      {initial.conflicts?.length > 0 && (
        <div role="status" className="rounded-lg px-3 py-2 text-[12px]" style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}>
          Both this draft and the active version changed {initial.conflicts.join(', ')}. The draft's values are kept; check them before saving.
        </div>
      )}
      <WorkflowGraph config={config} catalogue={catalogue} reasoner={reasoner} errors={check.errors} editing onSelect={setOpen} onChange={change} />
      {excludedSteps(config, catalogue).map((s) => (
        <div key={s.name} className="text-[12px] flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
          Not in this workflow: {s.label}
          <button type="button" aria-label={`Add ${s.name}`} onClick={() => change(addStep(config, s.name, catalogue))} className="px-2 py-0.5 rounded" style={{ border: '1px solid var(--border)' }}>
            Add
          </button>
        </div>
      ))}
      <SettingsForm config={config} schema={schema} onChange={(s, k, v) => change(setSetting(config, s, k, v))} />
      <CheckStatus check={check} />
      <label className="text-[12px] font-semibold flex flex-col gap-1" style={{ color: 'var(--text-primary)' }}>
        Change note
        <textarea maxLength={500} rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="text-[12px] rounded-lg px-2 py-1.5 font-normal" style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} placeholder="Why is the workflow changing?" />
      </label>
      <ErrorList error={save.error} />
      <div>
        <button type="button" disabled={!canSave} onClick={submit} className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40" style={{ background: 'var(--clr-blue)', color: '#FFFFFF' }}>
          {save.busy ? 'Saving…' : 'Save draft'}
        </button>
      </div>
      {open && (
        <StepPanel step={known[open]} config={config} schema={schema} reasoner={reasoner} onClose={() => setOpen(null)} />
      )}
    </section>
  );
}
```

Note: after writing, run the repo's formatter settings by eye — wrap long JSX lines the way neighbouring components do (one prop per line when a tag exceeds ~100 characters). Keep behaviour identical.

- [ ] **Step 6: Run the tests**

Run: `cd apps/console && npx vitest run` → all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/console/src/components/helix/workflow
git commit -m "feat: workflow draft editor with live server validation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Versions — history, diff, approve, reject, redraft, upload

**Files:**
- Create: `apps/console/src/components/helix/workflow/WorkflowDialog.jsx`
- Create: `apps/console/src/components/helix/workflow/VersionList.jsx`
- Create: `apps/console/src/components/helix/workflow/VersionDetail.jsx`
- Create: `apps/console/src/components/helix/workflow/YamlUpload.jsx`
- Test: `VersionDetail.test.jsx`, `VersionList.test.jsx`, `YamlUpload.test.jsx` in the same folder

**Interfaces:**
- Consumes: `fetchVersion`, `fetchRebased`, `approveVersion(n, key)`, `rejectVersion`, `uploadYaml`, `downloadYaml` (Task 9); `ErrorList` (Task 11); `Chip`, `TAG_STYLE`, `STATUS_TONE`, `describeChange`, `when` (Task 10); `Drawer`.
- Produces: `<WorkflowDialog title confirmLabel ready busy error onCancel onConfirm>{children}</WorkflowDialog>`; `<StatusChip status />` and `<VersionList versions selected onSelect />` (both from `VersionList.jsx`); `<VersionDetail number caller onChanged() onRedraft({config, basedOn, conflicts}) />`; `<YamlUpload onUploaded(version) onClose />`.

- [ ] **Step 1: Write the failing tests**

Create `apps/console/src/components/helix/workflow/VersionList.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { VersionList } from './VersionList';

const versions = [
  { number: 4, status: 'draft', note: 'drop rank', drafted_by: 'praveen' },
  { number: 3, status: 'active', note: 'Lookback 180→90 days', drafted_by: 'praveen' },
  { number: 2, status: 'rejected', note: 'too aggressive', drafted_by: 'asha' },
];

it('lists every version with its status, and selects one', async () => {
  const onSelect = vi.fn();
  render(<VersionList versions={versions} selected={3} onSelect={onSelect} />);
  expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
    expect.stringContaining('v4draft'),
    expect.stringContaining('v3active'),
    expect.stringContaining('v2rejected'),
  ]);
  expect(screen.getByRole('button', { current: true })).toHaveTextContent('v3');
  await userEvent.click(screen.getByRole('button', { name: /^v4/ }));
  expect(onSelect).toHaveBeenCalledWith(4);
});
```

Create `apps/console/src/components/helix/workflow/VersionDetail.test.jsx`:

```jsx
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../data/workflowApi';
import { VersionDetail } from './VersionDetail';

vi.mock('../data/workflowApi', () => ({
  fetchVersion: vi.fn(),
  fetchRebased: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));

const PRAVEEN = { id: 'praveen', roles: ['FO', 'PC'] };
const ASHA = { id: 'asha', roles: ['PC'] };

const draft = (over = {}) => ({
  number: 4,
  status: 'draft',
  note: 'Lookback 180→90 days',
  based_on: 3,
  active_number: 3,
  drafted_by: 'praveen',
  drafted_at: '2026-09-24T14:02:00+00:00',
  decided_by: null,
  decided_at: null,
  reject_reason: null,
  diff: [
    { path: 'settings.gather.priors_lookback_days', kind: 'changed', before: 180, after: 90 },
    { path: 'steps.rank', kind: 'removed', before: 4, after: null },
    { path: 'pause_before.reason', kind: 'added', before: null, after: null },
  ],
  ...over,
});

const renderDetail = (caller = ASHA, version = draft()) => {
  api.fetchVersion.mockResolvedValue(version);
  const props = { onChanged: vi.fn(), onRedraft: vi.fn() };
  render(<VersionDetail number={version.number} caller={caller} {...props} />);
  return props;
};

beforeEach(() => vi.clearAllMocks());

describe('VersionDetail', () => {
  it('reads every change against the active version', async () => {
    renderDetail();
    expect(await screen.findByText('gather.priors_lookback_days: 180 → 90')).toBeInTheDocument();
    expect(screen.getByText('rank removed (was step 5)')).toBeInTheDocument();
    expect(screen.getByText('pause added before reason')).toBeInTheDocument();
  });

  it('will not let the drafter approve their own draft', async () => {
    renderDetail(PRAVEEN);
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeDisabled();
    expect(screen.getByText('A second PC user must approve')).toBeInTheDocument();
  });

  it('approves only after both confirmations, with one key per confirmation', async () => {
    api.approveVersion.mockResolvedValue({ number: 4, status: 'active' });
    const { onChanged } = renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Approve and activate' });
    expect(confirm).toBeDisabled();
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(confirm);
    expect(api.approveVersion).toHaveBeenCalledWith(4, expect.any(String));
    expect(onChanged).toHaveBeenCalled();
  });

  it('keeps the dialog open with the server’s reason when approval fails', async () => {
    api.approveVersion.mockRejectedValue(new Error('v5 went live after this was drafted'));
    renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve and activate' }));
    expect(await within(dialog).findByText(/went live/)).toBeInTheDocument();
  });

  it('offers a redraft for a stale draft instead of approval', async () => {
    api.fetchRebased.mockResolvedValue({ config: { steps: [] }, based_on: 5, conflicts: ['steps'], errors: [] });
    const { onRedraft } = renderDetail(ASHA, draft({ active_number: 5 }));
    expect(await screen.findByText('v5 went live after this was drafted.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Redraft on v5' }));
    expect(onRedraft).toHaveBeenCalledWith({ config: { steps: [] }, basedOn: 5, conflicts: ['steps'] });
  });

  it('requires a reason to reject', async () => {
    api.rejectVersion.mockResolvedValue({ number: 4, status: 'rejected' });
    const { onChanged } = renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Reject' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Reject draft' });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'too aggressive');
    await userEvent.click(confirm);
    expect(api.rejectVersion).toHaveBeenCalledWith(4, 'too aggressive');
    expect(onChanged).toHaveBeenCalled();
  });

  it('says so when a version is the active one', async () => {
    renderDetail(ASHA, draft({ number: 3, status: 'active', diff: [] }));
    expect(await screen.findByText('This is the active version.')).toBeInTheDocument();
  });
});
```

Create `apps/console/src/components/helix/workflow/YamlUpload.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import * as api from '../data/workflowApi';
import { YamlUpload } from './YamlUpload';

vi.mock('../data/workflowApi', () => ({ uploadYaml: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

const fill = async () => {
  await userEvent.type(screen.getByLabelText('YAML text'), 'steps: []');
  await userEvent.type(screen.getByLabelText('Change note'), 'from the repo');
};

it('turns pasted YAML into a draft', async () => {
  api.uploadYaml.mockResolvedValue({ number: 5, status: 'draft' });
  const onUploaded = vi.fn();
  render(<YamlUpload onUploaded={onUploaded} onClose={vi.fn()} />);
  await fill();
  await userEvent.click(screen.getByRole('button', { name: 'Create draft' }));
  expect(api.uploadYaml).toHaveBeenCalledWith({ yaml: 'steps: []', note: 'from the repo' });
  expect(onUploaded).toHaveBeenCalledWith({ number: 5, status: 'draft' });
});

it('shows the server’s line-numbered problems', async () => {
  api.uploadYaml.mockRejectedValue(
    new ApiError('the YAML could not be read', {
      status: 422,
      errors: ["line 3, column 7: expected ',' or ']'"],
    }),
  );
  render(<YamlUpload onUploaded={vi.fn()} onClose={vi.fn()} />);
  await fill();
  await userEvent.click(screen.getByRole('button', { name: 'Create draft' }));
  expect(await screen.findByText(/line 3, column 7/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/console && npx vitest run src/components/helix/workflow`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the dialog**

Create `apps/console/src/components/helix/workflow/WorkflowDialog.jsx`:

```jsx
import { useEffect } from 'react';
import { manrope } from '../lib/format';

/** A confirm dialog styled like the adjustments ConfirmDialog. */
export function WorkflowDialog({ title, confirmLabel, ready, busy, error, onCancel, onConfirm, children }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onCancel();
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [onCancel]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,20,50,0.45)', backdropFilter: 'blur(2px)' }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-dialog-title"
    >
      <div
        className="w-full max-w-[480px] rounded-2xl overflow-hidden"
        style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow-md)' }}
      >
        <div id="workflow-dialog-title" className="px-5 py-4 text-[15px] font-bold" style={{ ...manrope, color: 'var(--text-primary)', borderBottom: '1px solid var(--border)' }}>
          {title}
        </div>
        <div className="px-5 py-4 flex flex-col gap-2">
          {children}
          {error && (
            <div role="alert" className="text-[12px]" style={{ color: 'var(--clr-red)' }}>
              {error}
            </div>
          )}
        </div>
        <div className="px-5 py-3 flex justify-end gap-2" style={{ borderTop: '1px solid var(--border)' }}>
          <button type="button" onClick={onCancel} className="text-[12px] px-3 py-1.5 rounded-full" style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
            Cancel
          </button>
          <button type="button" disabled={!ready || busy} onClick={onConfirm} className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40" style={{ background: 'var(--clr-blue)', color: '#FFFFFF' }}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function Check({ checked, onChange, children }) {
  return (
    <label className="flex items-start gap-2 text-[12px] rounded-lg px-2.5 py-2 cursor-pointer" style={{ background: 'var(--bg-muted)', color: 'var(--text-secondary)' }}>
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}
```

- [ ] **Step 4: Implement the list**

Create `apps/console/src/components/helix/workflow/VersionList.jsx`:

```jsx
import { Chip } from './StepCard';
import { STATUS_TONE } from './workflowModel';

export const StatusChip = ({ status }) => <Chip label={status} tone={STATUS_TONE[status] || 'grey'} />;

export function VersionList({ versions, selected, onSelect }) {
  return (
    <ul aria-label="Workflow versions" className="flex flex-col gap-1">
      {versions.map((v) => (
        <li key={v.number}>
          <button
            type="button"
            onClick={() => onSelect(v.number)}
            aria-current={selected === v.number ? 'true' : undefined}
            className="w-full text-left rounded-lg px-3 py-2"
            style={{
              background: selected === v.number ? 'var(--bg-hover)' : 'transparent',
              border: '1px solid var(--border)',
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-bold" style={{ color: 'var(--text-primary)' }}>
                v{v.number}
              </span>
              <StatusChip status={v.status} />
              <span className="ml-auto text-[10.5px]" style={{ color: 'var(--text-muted)' }}>
                {v.drafted_by}
              </span>
            </div>
            <div className="text-[11.5px] truncate" style={{ color: 'var(--text-secondary)' }}>
              {v.note}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 5: Implement the detail**

Create `apps/console/src/components/helix/workflow/VersionDetail.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { approveVersion, downloadYaml, fetchRebased, fetchVersion, rejectVersion } from '../data/workflowApi';
import { StatusChip } from './VersionList';
import { Check, WorkflowDialog } from './WorkflowDialog';
import { describeChange, when } from './workflowModel';

const pillButton = 'text-[12px] font-semibold px-3 py-1.5 rounded-full disabled:opacity-40';

function ApproveDialog({ version, onCancel, onDone }) {
  // One key per confirmation: a retried click can never approve twice.
  const [key] = useState(() => crypto.randomUUID());
  const [ackDiff, setAckDiff] = useState(false);
  const [ackLive, setAckLive] = useState(false);
  const [state, setState] = useState({ busy: false, error: null });
  const confirm = async () => {
    setState({ busy: true, error: null });
    try {
      await approveVersion(version.number, key);
      onDone();
    } catch (e) {
      setState({ busy: false, error: e.message });
    }
  };
  return (
    <WorkflowDialog title={`Approve v${version.number}`} confirmLabel="Approve and activate" ready={ackDiff && ackLive} {...state} onCancel={onCancel} onConfirm={confirm}>
      <Check checked={ackDiff} onChange={setAckDiff}>
        I have reviewed every change against v{version.active_number}.
      </Check>
      <Check checked={ackLive} onChange={setAckLive}>
        New investigations run on v{version.number} from now on. Runs already started keep their version.
      </Check>
    </WorkflowDialog>
  );
}

function RejectDialog({ version, own, onCancel, onDone }) {
  const [reason, setReason] = useState('');
  const [state, setState] = useState({ busy: false, error: null });
  const confirm = async () => {
    setState({ busy: true, error: null });
    try {
      await rejectVersion(version.number, reason.trim());
      onDone();
    } catch (e) {
      setState({ busy: false, error: e.message });
    }
  };
  return (
    <WorkflowDialog title={`${own ? 'Withdraw' : 'Reject'} v${version.number}`} confirmLabel="Reject draft" ready={reason.trim().length > 0} {...state} onCancel={onCancel} onConfirm={confirm}>
      <label className="text-[12px] font-semibold flex flex-col gap-1" style={{ color: 'var(--text-primary)' }}>
        Reason
        <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} className="text-[12px] rounded-lg px-2 py-1.5 font-normal" style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
      </label>
    </WorkflowDialog>
  );
}

function Changes({ v }) {
  if (v.number === v.active_number) {
    return <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>This is the active version.</p>;
  }
  return (
    <div>
      <h4 className="text-[11px] font-bold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
        Compared with active v{v.active_number}
      </h4>
      {v.diff.length ? (
        <ul className="list-disc pl-4 text-[12.5px]" style={{ color: 'var(--text-primary)' }}>
          {v.diff.map((c) => (
            <li key={`${c.path}-${c.kind}`}>{describeChange(c)}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>Identical to the active version.</p>
      )}
    </div>
  );
}

function Actions({ v, caller, onApprove, onReject, onRedraft, redraftError }) {
  const isPc = caller?.roles?.includes('PC');
  const own = v.drafted_by === caller?.id;
  const stale = v.based_on !== v.active_number;
  return (
    <div className="flex flex-col gap-2">
      {stale ? (
        <div className="rounded-lg px-3 py-2 text-[12px] flex flex-col gap-1.5" style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}>
          <span>v{v.active_number} went live after this was drafted.</span>
          <button type="button" onClick={onRedraft} disabled={!isPc} className={pillButton} style={{ border: '1px solid var(--clr-amber)' }}>
            Redraft on v{v.active_number}
          </button>
          {redraftError && <span role="alert">{redraftError}</span>}
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          <button type="button" disabled={own || !isPc} onClick={onApprove} className={pillButton} style={{ background: 'var(--clr-green)', color: '#FFFFFF' }}>
            Approve
          </button>
          {own && <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>A second PC user must approve</span>}
        </div>
      )}
      {isPc && (
        <button type="button" onClick={onReject} className={pillButton} style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          {own ? 'Withdraw' : 'Reject'}
        </button>
      )}
    </div>
  );
}

export function VersionDetail({ number, caller, onChanged, onRedraft }) {
  const [state, setState] = useState({ status: 'loading' });
  const [dialog, setDialog] = useState(null);
  const [redraftError, setRedraftError] = useState(null);
  useEffect(() => {
    let live = true;
    fetchVersion(number)
      .then((v) => live && setState({ status: 'ready', v }))
      .catch((e) => live && setState({ status: 'error', error: e.message }));
    return () => {
      live = false;
    };
  }, [number]);

  if (state.status === 'loading') return <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>Loading v{number}…</p>;
  if (state.status === 'error') return <p role="alert" className="text-[12px]" style={{ color: 'var(--clr-red)' }}>{state.error}</p>;
  const { v } = state;
  const redraft = async () => {
    setRedraftError(null);
    try {
      const body = await fetchRebased(v.number);
      onRedraft({ config: body.config, basedOn: body.based_on, conflicts: body.conflicts });
    } catch (e) {
      setRedraftError(e.message);
    }
  };
  const done = () => {
    setDialog(null);
    onChanged();
  };
  const decided = v.decided_by && `${v.status === 'rejected' ? 'rejected' : 'approved'} by ${v.decided_by} · ${when(v.decided_at)}`;
  return (
    <section aria-label={`Version ${v.number}`} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h3 className="text-[15px] font-bold" style={{ color: 'var(--text-primary)' }}>v{v.number}</h3>
        <StatusChip status={v.status} />
        <button type="button" onClick={() => downloadYaml(v.number)} className="ml-auto text-[11px] underline" style={{ color: 'var(--text-secondary)' }}>
          Download YAML
        </button>
      </div>
      <p className="text-[11.5px]" style={{ color: 'var(--text-muted)' }}>
        Drafted by {v.drafted_by} · {when(v.drafted_at)}
        {decided && ` · ${decided}`}
      </p>
      <blockquote className="text-[12.5px] pl-2" style={{ borderLeft: '2px solid var(--border)', color: 'var(--text-primary)' }}>
        {v.note}
      </blockquote>
      {v.reject_reason && <p className="text-[12px]" style={{ color: 'var(--clr-red)' }}>Rejected: {v.reject_reason}</p>}
      <Changes v={v} />
      {v.status === 'draft' && (
        <Actions v={v} caller={caller} onApprove={() => setDialog('approve')} onReject={() => setDialog('reject')} onRedraft={redraft} redraftError={redraftError} />
      )}
      {dialog === 'approve' && <ApproveDialog version={v} onCancel={() => setDialog(null)} onDone={done} />}
      {dialog === 'reject' && <RejectDialog version={v} own={v.drafted_by === caller?.id} onCancel={() => setDialog(null)} onDone={done} />}
    </section>
  );
}
```

- [ ] **Step 6: Implement the upload drawer**

Create `apps/console/src/components/helix/workflow/YamlUpload.jsx`:

```jsx
import { useState } from 'react';
import { uploadYaml } from '../data/workflowApi';
import { Drawer } from '../ui/Drawer';
import { ErrorList } from './ErrorList';

const fieldStyle = { background: 'var(--bg-muted)', border: '1px solid var(--border)', color: 'var(--text-primary)' };

export function YamlUpload({ onUploaded, onClose }) {
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [state, setState] = useState({ busy: false, error: null });
  const pick = async (e) => {
    const file = e.target.files?.[0];
    if (file) setText(await file.text());
  };
  const submit = async () => {
    setState({ busy: true, error: null });
    try {
      onUploaded(await uploadYaml({ yaml: text, note: note.trim() }));
    } catch (e) {
      setState({ busy: false, error: e });
    }
  };
  const ready = text.trim() && note.trim() && !state.busy;
  return (
    <Drawer title="Upload YAML" subtitle="It becomes a draft. A second Product Control user must approve it." width={560} onClose={onClose}>
      <div className="flex flex-col gap-3 text-[12px]" style={{ color: 'var(--text-primary)' }}>
        <label className="flex flex-col gap-1 font-semibold">
          YAML file
          <input type="file" accept=".yaml,.yml,text/yaml" onChange={pick} className="font-normal" />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Or paste it
          <textarea aria-label="YAML text" rows={14} value={text} onChange={(e) => setText(e.target.value)} className="rounded-lg px-2 py-1.5 font-mono text-[11.5px]" style={fieldStyle} />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Change note
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} className="rounded-lg px-2 py-1.5 font-normal" style={fieldStyle} />
        </label>
        <ErrorList error={state.error} />
        <div>
          <button type="button" disabled={!ready} onClick={submit} className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40" style={{ background: 'var(--clr-blue)', color: '#FFFFFF' }}>
            {state.busy ? 'Uploading…' : 'Create draft'}
          </button>
        </div>
      </div>
    </Drawer>
  );
}
```

- [ ] **Step 7: Run the tests**

Run: `cd apps/console && npx vitest run` → all pass.

- [ ] **Step 8: Commit**

```bash
git add apps/console/src/components/helix/workflow
git commit -m "feat: workflow versions — diff, four-eyes approve, reject, redraft, YAML upload

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: The Workflow tab in Helix

**Files:**
- Create: `apps/console/src/components/helix/workflow/ActiveStrip.jsx`
- Create: `apps/console/src/components/helix/workflow/DevCallerSwitch.jsx`
- Create: `apps/console/src/components/helix/workflow/WorkflowView.jsx`
- Modify: `apps/console/src/components/helix/HelixApp.jsx`
- Modify: `apps/console/src/components/fobo/execution/WorkflowTrace.jsx:33-39`
- Test: `apps/console/src/components/helix/workflow/WorkflowView.test.jsx`; extend `apps/console/src/components/helix/HelixApp.test.jsx`

**Interfaces:**
- Consumes: everything from Tasks 9–12; `setDevCaller` (Task 9); board field `devCallers` (Task 1).
- Produces: `<WorkflowView callerKey />`, `<ActiveStrip overview canDraft onNewDraft onUpload onShowDrafts />`, `<DevCallerSwitch callers current onSwitch />`.

- [ ] **Step 1: Write the failing tests**

Create `apps/console/src/components/helix/workflow/WorkflowView.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../data/workflowApi';
import fixture from './__fixtures__/workflow.json';
import { WorkflowView } from './WorkflowView';

vi.mock('../data/workflowApi', () => ({
  fetchWorkflow: vi.fn(),
  fetchVersions: vi.fn(),
  fetchVersion: vi.fn(),
  fetchRebased: vi.fn(),
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
  uploadYaml: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));

const history = [
  { number: 5, status: 'draft', note: 'drop rank', based_on: 3, drafted_by: 'asha' },
  { number: 4, status: 'draft', note: 'pause before reason', based_on: 3, drafted_by: 'praveen' },
  { number: 3, status: 'active', note: 'Lookback 180→90 days', based_on: 2, drafted_by: 'praveen' },
];

const overview = (over = {}) => ({ ...structuredClone(fixture), ...over });

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchWorkflow.mockResolvedValue(overview());
  api.fetchVersions.mockResolvedValue(history);
  api.fetchVersion.mockImplementation(async (n) => ({
    ...history.find((v) => v.number === n),
    active_number: 3,
    diff: [],
    drafted_at: '2026-09-24T14:02:00+00:00',
  }));
  api.validateWorkflow.mockResolvedValue({ ok: true, errors: [] });
});

describe('WorkflowView', () => {
  it('shows the active version, the pending drafts and the graph', async () => {
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2 drafts awaiting approval' })).toBeInTheDocument();
    expect(screen.getAllByTestId('step-card')).toHaveLength(fixture.active.config.steps.length);
  });

  it('opens the first pending draft', async () => {
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByRole('region', { name: 'Version 5' })).toBeInTheDocument();
  });

  it('warns when the server overrides the approved reasoner', async () => {
    api.fetchWorkflow.mockResolvedValue(overview({ overrides: { reasoner: 'direct' } }));
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByText(/overridden to/)).toHaveTextContent('direct');
  });

  it('starts a draft from the active version', async () => {
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'New draft' }));
    expect(screen.getByRole('region', { name: 'Draft editor' })).toHaveTextContent('based on v3');
  });

  it('does not offer drafting to a caller without Product Control', async () => {
    api.fetchWorkflow.mockResolvedValue(overview({ caller: { id: 'fo-user', roles: ['FO'] } }));
    render(<WorkflowView callerKey="fo-user" />);
    expect(await screen.findByRole('button', { name: 'New draft' })).toBeDisabled();
  });

  it('offers a retry when the workflow cannot be loaded', async () => {
    api.fetchWorkflow.mockRejectedValueOnce(new Error('GET /api/workflow failed: 500'));
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
  });
});
```

In `apps/console/src/components/helix/HelixApp.test.jsx`, add the mock for the workflow API next to the existing `vi.mock('./data/helixApi', ...)`:

```jsx
vi.mock('./data/workflowApi', () => ({
  fetchWorkflow: vi.fn(async () => structuredClone(workflowFixture)),
  fetchVersions: vi.fn(async () => []),
  fetchVersion: vi.fn(async () => ({ ...workflowFixture.active, active_number: 3, diff: [] })),
  fetchRebased: vi.fn(),
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
  uploadYaml: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));
```

with `import workflowFixture from './workflow/__fixtures__/workflow.json';` at the top, and add these tests inside the `describe('HelixApp', ...)` block:

```jsx
  it('opens the Workflow tab', async () => {
    await renderLoaded();
    await userEvent.click(screen.getByRole('button', { name: 'Workflow' }));
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
  });

  it('offers the dev caller switch only when the API lists dev callers', async () => {
    const data = served();
    data.devCallers = [
      { id: 'praveen', roles: ['FO', 'PC'] },
      { id: 'asha', roles: ['PC'] },
    ];
    await renderLoaded(data);
    api.fetchBoard.mockClear();
    await userEvent.selectOptions(screen.getByLabelText('Act as'), 'asha');
    expect(window.localStorage.getItem('fobo.devCaller')).toBe('asha');
    expect(api.fetchBoard).toHaveBeenCalled();
    window.localStorage.removeItem('fobo.devCaller');
  });

  it('shows no dev caller switch without dev callers', async () => {
    await renderLoaded();
    expect(screen.queryByLabelText('Act as')).toBeNull();
  });
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd apps/console && npx vitest run src/components/helix`
Expected: FAIL — `WorkflowView` missing; HelixApp has no Workflow tab.

- [ ] **Step 3: Implement the strip and the switch**

Create `apps/console/src/components/helix/workflow/ActiveStrip.jsx`:

```jsx
import { downloadYaml } from '../data/workflowApi';
import { manrope } from '../lib/format';
import { StatusChip } from './VersionList';
import { when } from './workflowModel';

const pill = 'text-[12px] font-semibold px-3 py-1.5 rounded-full disabled:opacity-40';

const provenance = (a) =>
  [
    `drafted by ${a.drafted_by}`,
    a.decided_by && `approved by ${a.decided_by}`,
    when(a.decided_at),
    a.note && `“${a.note}”`,
  ]
    .filter(Boolean)
    .join(' · ');

export function ActiveStrip({ overview, canDraft, onNewDraft, onUpload, onShowDrafts }) {
  const { active, pending_drafts: pending, overrides } = overview;
  return (
    <div className="rounded-2xl px-4 py-3 flex flex-col gap-2" style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[16px] font-extrabold" style={{ ...manrope, color: 'var(--text-primary)' }}>
          Workflow v{active.number}
        </span>
        <StatusChip status="active" />
        <span className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          {provenance(active)}
        </span>
        {pending > 0 && (
          <button type="button" onClick={onShowDrafts} className={pill} style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}>
            {pending} draft{pending === 1 ? '' : 's'} awaiting approval
          </button>
        )}
        <div className="ml-auto flex gap-2 flex-wrap">
          <button type="button" onClick={() => downloadYaml(active.number)} className={pill} style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
            Download YAML
          </button>
          <button type="button" onClick={onUpload} disabled={!canDraft} className={pill} style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
            Upload YAML
          </button>
          <button type="button" onClick={onNewDraft} disabled={!canDraft} title={canDraft ? undefined : 'Only Product Control can draft a change'} className={pill} style={{ background: 'var(--clr-blue)', color: '#FFFFFF' }}>
            New draft
          </button>
        </div>
      </div>
      {overrides?.reasoner && (
        <div role="status" className="rounded-lg px-3 py-2 text-[12px]" style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}>
          Reasoner overridden to <code>{overrides.reasoner}</code> on this server by FOBO_REASONER. The approved setting is <code>{active.config.settings.reason.reasoner}</code>.
        </div>
      )}
    </div>
  );
}
```

Create `apps/console/src/components/helix/workflow/DevCallerSwitch.jsx`:

```jsx
import { setDevCaller } from '@/lib/apiClient';

/** Dev only: act as another caller, so a second person can approve a draft. */
export function DevCallerSwitch({ callers, current, onSwitch }) {
  if (!callers?.length) return null;
  return (
    <label className="flex items-center gap-1 text-[10px]" style={{ color: 'var(--text-on-brand2)' }}>
      Act as
      <select
        aria-label="Act as"
        value={current || ''}
        onChange={(e) => {
          setDevCaller(e.target.value);
          onSwitch(e.target.value);
        }}
        className="text-[11px] rounded px-1 py-0.5"
        style={{ background: 'var(--bg-header-deep)', color: '#FFFFFF', border: '1px solid rgba(255,255,255,0.2)' }}
      >
        {callers.map((c) => (
          <option key={c.id} value={c.id}>
            {c.id} ({c.roles.join(', ')})
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 4: Implement the view**

Create `apps/console/src/components/helix/workflow/WorkflowView.jsx`:

```jsx
import { useCallback, useEffect, useState } from 'react';
import { fetchVersions, fetchWorkflow } from '../data/workflowApi';
import { ActiveStrip } from './ActiveStrip';
import { DraftEditor } from './DraftEditor';
import { StepPanel } from './StepPanel';
import { VersionDetail } from './VersionDetail';
import { VersionList } from './VersionList';
import { WorkflowGraph } from './WorkflowGraph';
import { YamlUpload } from './YamlUpload';
import { byName, effectiveReasoner } from './workflowModel';

function Card({ title, children }) {
  return (
    <div className="rounded-2xl px-4 py-3" style={{ background: 'var(--bg-card-solid)', border: '1px solid var(--border)', boxShadow: 'var(--card-shadow)' }}>
      {title && (
        <h3 className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: 'var(--text-muted)' }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

const firstDraft = (history) => history.find((v) => v.status === 'draft')?.number;

export function WorkflowView({ callerKey }) {
  const [load, setLoad] = useState({ state: 'loading' });
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState(null);
  const [generation, setGeneration] = useState(0);
  const [mode, setMode] = useState({ kind: 'view' });
  const [panel, setPanel] = useState(null);
  const [uploading, setUploading] = useState(false);

  const reload = useCallback(async (select) => {
    try {
      const [overview, versions] = await Promise.all([fetchWorkflow(), fetchVersions()]);
      setLoad({ state: 'ready', overview });
      setHistory(versions);
      setSelected((cur) => select ?? cur ?? firstDraft(versions) ?? overview.active.number);
      setGeneration((g) => g + 1);
    } catch (e) {
      setLoad({ state: 'error', error: e.message });
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload, callerKey]);

  if (load.state === 'loading') {
    return <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>Loading the workflow…</p>;
  }
  if (load.state === 'error') {
    return (
      <div className="flex items-center gap-3 text-[12px]" style={{ color: 'var(--clr-red)' }}>
        {load.error}
        <button type="button" onClick={() => { setLoad({ state: 'loading' }); reload(); }} className="px-3 py-1 rounded-full" style={{ border: '1px solid var(--border)' }}>
          Retry
        </button>
      </div>
    );
  }

  const { overview } = load;
  const known = byName(overview.steps);
  const reasoner = effectiveReasoner(overview.active.config, overview.overrides);
  const isPc = overview.caller.roles.includes('PC');
  const editing = mode.kind === 'edit';

  return (
    <div className="flex flex-col gap-4">
      <ActiveStrip
        overview={overview}
        canDraft={isPc && !editing}
        onNewDraft={() => setMode({ kind: 'edit', initial: { config: overview.active.config, basedOn: overview.active.number, conflicts: [] } })}
        onUpload={() => setUploading(true)}
        onShowDrafts={() => setSelected(firstDraft(history) ?? selected)}
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0">
          {editing ? (
            <Card>
              <DraftEditor
                key={`${mode.initial.basedOn}-${generation}`}
                initial={mode.initial}
                catalogue={overview.steps}
                schema={overview.settings_schema}
                overrides={overview.overrides}
                onCancel={() => setMode({ kind: 'view' })}
                onSaved={(v) => {
                  setMode({ kind: 'view' });
                  reload(v.number);
                }}
              />
            </Card>
          ) : (
            <Card title={`Active workflow · v${overview.active.number}`}>
              <WorkflowGraph config={overview.active.config} catalogue={overview.steps} reasoner={reasoner} onSelect={setPanel} />
            </Card>
          )}
        </div>
        <aside className="flex flex-col gap-3 min-w-0">
          <Card title="Versions">
            <VersionList versions={history} selected={selected} onSelect={setSelected} />
          </Card>
          {selected != null && (
            <Card>
              <VersionDetail
                key={`${selected}-${generation}`}
                number={selected}
                caller={overview.caller}
                onChanged={() => reload(selected)}
                onRedraft={(initial) => setMode({ kind: 'edit', initial })}
              />
            </Card>
          )}
        </aside>
      </div>
      {panel && (
        <StepPanel step={known[panel]} config={overview.active.config} schema={overview.settings_schema} reasoner={reasoner} onClose={() => setPanel(null)} />
      )}
      {uploading && (
        <YamlUpload
          onClose={() => setUploading(false)}
          onUploaded={(v) => {
            setUploading(false);
            reload(v.number);
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Add the tab and the switch to Helix**

In `apps/console/src/components/helix/HelixApp.jsx`:

1. Imports: change the lucide import to `import { CalendarDays as Calendar, Gauge, Workflow as WorkflowIcon } from 'lucide-react';` and add `import { DevCallerSwitch } from './workflow/DevCallerSwitch';` and `import { WorkflowView } from './workflow/WorkflowView';`.
2. State: add `const [devCallers, setDevCallers] = useState([]);` after `const [caller, setCaller] = useState(null);`.
3. In `loadBoard`, after `setCaller(board.caller);` add `setDevCallers(board.devCallers || []);`.
4. After the Agent Analytics tab button, add:

```jsx
              <button
                onClick={() => setView('workflow')}
                className="text-xs font-semibold px-3.5 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
                style={tabStyle(view === 'workflow')}
              >
                <WorkflowIcon size={12} />
                {' Workflow'}
              </button>
```

5. In the header's right-hand block, directly before `<NotificationBell`, add:

```jsx
              <DevCallerSwitch callers={devCallers} current={caller?.id} onSwitch={() => loadBoard()} />
```

6. Replace the `{view === 'analytics' ? ( … ) : ( … )}` expression's opening so the workflow view renders first:

```jsx
        {view === 'workflow' ? (
          <div className="flex-1 min-h-0 overflow-y-auto px-6 md:px-10 py-6">
            <div className="max-w-7xl mx-auto w-full">
              <WorkflowView callerKey={caller?.id} />
            </div>
          </div>
        ) : view === 'analytics' ? (
```

(the existing analytics and pipeline branches follow unchanged).

- [ ] **Step 6: The classic Execution tab names the version, not the file**

In `apps/console/src/components/fobo/execution/WorkflowTrace.jsx`, replace the `<p className="text-[11px] -mt-2" …>…</p>` block (lines 33–39) with:

```jsx
      <p className="text-[11px] -mt-2" style={{ color: 'var(--text-muted)' }}>
        Steps, order and pause points from workflow
        {trace.workflow_version ? ` v${trace.workflow_version}` : ''}, as approved in the
        Workflow tab.
      </p>
```

- [ ] **Step 7: Run the tests**

Run: `cd apps/console && npx vitest run` → all pass.

- [ ] **Step 8: Check it in the browser**

With the API running (`cd apps/api && FOBO_ENV=dev .venv/bin/uvicorn api.main:app --port 8100 --reload`) and the console (`cd apps/console && npm run dev`), open `http://localhost:3100/fobo`, click **Workflow**, and confirm: the graph shows nine steps with tags; **New draft** opens the editor; the "Act as" switch appears in the header. Check dark mode and a 375 px-wide window (cards stack vertically, no horizontal scroll).

- [ ] **Step 9: Commit**

```bash
git add apps/console/src
git commit -m "feat: Workflow tab in Helix, with a dev caller switch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: End-to-end test, CORS for a second console, docs

**Files:**
- Modify: `apps/api/api/main.py` (CORS origins from `FOBO_CONSOLE_ORIGINS`)
- Test: `apps/api/tests/test_cors.py`
- Create: `apps/api/scripts/reset_e2e_db.py`
- Modify: `apps/console/next.config.mjs`, `apps/console/package.json`
- Create: `apps/console/playwright.config.js`, `apps/console/e2e/reset-db.mjs`, `apps/console/e2e/workflow.spec.js`
- Modify: `.gitignore`, `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: `npm run test:e2e` in `apps/console`.

- [ ] **Step 1: Write the failing CORS test**

Create `apps/api/tests/test_cors.py`:

```python
"""The console origin is configurable, so an e2e console can run beside the dev one."""

from httpx import ASGITransport, AsyncClient

from api.main import create_app


async def _preflight(origin: str):
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        return await c.options("/health", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})


async def test_the_dev_console_is_allowed_by_default(monkeypatch):
    monkeypatch.delenv("FOBO_CONSOLE_ORIGINS", raising=False)
    r = await _preflight("http://localhost:3100")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3100"


async def test_extra_origins_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("FOBO_CONSOLE_ORIGINS", "http://localhost:3100, http://localhost:3101")
    r = await _preflight("http://localhost:3101")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3101"
```

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_cors.py -q` → the second test FAILS.

- [ ] **Step 2: Configurable origins**

In `apps/api/api/main.py`, add `import os`, replace `CONSOLE_ORIGIN = "http://localhost:3100"` with:

```python
def _console_origins() -> list[str]:
    """The consoles allowed to call the API. FOBO_CONSOLE_ORIGINS is a
    comma-separated list; the e2e console runs on its own port."""
    raw = os.getenv("FOBO_CONSOLE_ORIGINS", "http://localhost:3100")
    return [o.strip() for o in raw.split(",") if o.strip()]
```

and pass `allow_origins=_console_origins()` to `CORSMiddleware`. Run `grep -rn CONSOLE_ORIGIN apps/api --include='*.py'` and update any remaining reference. Run the CORS tests → PASS; full suite → all pass.

- [ ] **Step 3: A disposable e2e database**

Create `apps/api/scripts/reset_e2e_db.py`:

```python
"""Create an empty fobo_e2e database with the current schema.

    FOBO_DATABASE_URL=postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e \
        .venv/bin/python scripts/reset_e2e_db.py

Refuses any other database name: it drops the database it is pointed at.
"""

import asyncio
import os
import sys

import asyncpg
from sqlalchemy import text

URL = os.environ.get("FOBO_DATABASE_URL", "")
NAME = "fobo_e2e"


async def main() -> None:
    raw = URL.replace("+asyncpg", "")
    admin = raw.rsplit("/", 1)[0] + "/postgres"
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{NAME}"')
    finally:
        await conn.close()

    from app.db import models_graph, models_ops, models_session, models_workflow  # noqa: F401
    from app.db.base import Base, engine

    async with engine.begin() as c:
        await c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await c.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    if not URL.endswith(f"/{NAME}"):
        sys.exit(f"refusing: FOBO_DATABASE_URL must point at the {NAME} database")
    asyncio.run(main())
```

Run it once by hand to check it: `cd apps/api && FOBO_DATABASE_URL=postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e .venv/bin/python scripts/reset_e2e_db.py` → exits 0. Run it with the dev URL → exits with "refusing".

- [ ] **Step 4: Let a second Next server use its own build directory**

Replace `apps/console/next.config.mjs` with:

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // The e2e console runs beside the dev one; its own directory keeps the two
  // dev servers from sharing (and locking) .next.
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
```

Add to `.gitignore`: `.next-e2e/`, `apps/console/test-results/`, `apps/console/playwright-report/`.

- [ ] **Step 5: Install Playwright and write the config**

Run: `cd apps/console && npm install -D @playwright/test && npx playwright install chromium`.

Add to `apps/console/package.json` scripts: `"test:e2e": "node e2e/reset-db.mjs && playwright test"`.

Create `apps/console/e2e/reset-db.mjs`:

```js
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const api = fileURLToPath(new URL('../../api', import.meta.url));

execFileSync('.venv/bin/python', ['scripts/reset_e2e_db.py'], {
  cwd: api,
  stdio: 'inherit',
  env: {
    ...process.env,
    FOBO_DATABASE_URL: 'postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e',
  },
});
```

Create `apps/console/playwright.config.js`:

```js
import { defineConfig } from '@playwright/test';

const API = 'http://localhost:8101';
const CONSOLE = 'http://localhost:3101';

export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  workers: 1,
  use: { baseURL: CONSOLE, trace: 'retain-on-failure' },
  webServer: [
    {
      command: '.venv/bin/uvicorn api.main:app --port 8101',
      cwd: '../api',
      url: `${API}/health`,
      env: {
        FOBO_ENV: 'dev',
        FOBO_DATABASE_URL: 'postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e',
        FOBO_CONSOLE_ORIGINS: CONSOLE,
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npx next dev -p 3101',
      url: `${CONSOLE}/fobo`,
      env: { NEXT_PUBLIC_API_BASE: API, NEXT_DIST_DIR: '.next-e2e' },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
```

- [ ] **Step 6: Write the end-to-end test**

Create `apps/console/e2e/workflow.spec.js`:

```js
import { expect, test } from '@playwright/test';

const API = 'http://localhost:8101';

test('a draft goes live when a second controller approves it, and only new runs use it', async ({
  page,
  request,
}) => {
  await page.goto('/fobo');
  await expect(page.getByText('FOBO Controller')).toBeVisible({ timeout: 120_000 });

  // Loading the board ran R-1055's investigation on v1.
  await page.getByRole('button', { name: 'Workflow', exact: true }).click();
  await expect(page.getByText('Workflow v1', { exact: true })).toBeVisible();

  // praveen drafts a 90-day lookback.
  await page.getByRole('button', { name: 'New draft' }).click();
  await page.getByLabel('priors lookback days').fill('90');
  await page.getByLabel('Change note').fill('Lookback 180 to 90 days');
  await expect(page.getByText(/^Valid/)).toBeVisible();
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('button', { name: '1 draft awaiting approval' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeDisabled();

  // asha approves it.
  await page.getByLabel('Act as').selectOption('asha');
  await page.getByRole('button', { name: /^v2/ }).click();
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  const dialog = page.getByRole('dialog');
  for (const box of await dialog.getByRole('checkbox').all()) await box.check();
  await dialog.getByRole('button', { name: 'Approve and activate' }).click();
  await expect(page.getByText('Workflow v2', { exact: true })).toBeVisible();

  // A run that starts now uses v2.
  await request.get(`${API}/api/recs/R-2031`, { timeout: 120_000 });
  const fresh = await (await request.get(`${API}/api/recs/R-2031/trace`)).json();
  expect(fresh.trace.workflow_version).toBe(2);

  // The run that started on v1 keeps it.
  await page.getByRole('button', { name: 'Pipeline', exact: true }).click();
  await page.getByRole('button', { name: /Graph run/ }).click();
  await expect(page.getByText(/workflow v1 ·/)).toBeVisible();
});
```

- [ ] **Step 7: Run it**

Stop nothing: the dev servers on 8100/3100 may keep running. Run: `cd apps/console && npm run test:e2e`.
Expected: `1 passed`. If Next refuses to start a second dev server even with `NEXT_DIST_DIR`, change the second `webServer.command` to `npx next build && npx next start -p 3101` (same env) and re-run.

- [ ] **Step 8: Document it**

In `README.md`:

1. Change the API run command (currently `cd apps/api && .venv/bin/uvicorn api.main:app --port 8100 --reload`) to
   `cd apps/api && FOBO_ENV=dev .venv/bin/uvicorn api.main:app --port 8100 --reload`, and add one line under it: "`FOBO_ENV=dev` enables the **Act as** switch in the console header, so a second person can approve a workflow draft."
2. Add a migration note next to the existing alembic command: after pulling this change, run `cd apps/api && .venv/bin/alembic upgrade head`.
3. Replace the section that tells readers to edit `config/workflow/fobo-investigation.yaml` and restart the API with a **Workflow tab** section:
   - The live workflow is stored in the database; the YAML file seeds version 1 and is the Download/Upload format.
   - In the console, open **Workflow**: the graph shows each step tagged Code / Playbook + Reasoner / Template / Human, the pause before sign-off, and the escalate branch. Click a step for its inputs, outputs and settings.
   - **New draft** → edit (rank on/off, order, pauses, settings, reasoner); problems are listed as you edit → add a note → **Save draft**.
   - A different Product Control user opens the draft, reviews the changes against the active version, and approves (two confirmations). New investigations use it from then on; a run keeps the version it started with (see "workflow vN" in the Graph run drawer).
   - `FOBO_REASONER` still overrides the reasoner for local development; the Workflow tab shows a banner while it does.
4. Add under testing: `cd apps/console && npm run test:e2e` — runs the workflow end-to-end test against a fresh `fobo_e2e` database on ports 8101/3101.

- [ ] **Step 9: Commit**

```bash
git add apps/api/api/main.py apps/api/tests/test_cors.py apps/api/scripts/reset_e2e_db.py apps/console/next.config.mjs apps/console/package.json apps/console/package-lock.json apps/console/playwright.config.js apps/console/e2e .gitignore README.md
git commit -m "test: end-to-end four-eyes workflow change; docs for the Workflow tab

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
