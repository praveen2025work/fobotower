# FOBO Phase 2 — Real Data and Pipeline Screen Fidelity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every hardcoded literal in the console and API with a value derived from the database, and build the pipeline screen features the mock has and Phase 1 omitted: the Grounding MCP-call panel, per-break reasons and badges, approve/reject controls, and the pattern and book detail drawers.

**Architecture:** Unchanged from Phase 1 — LangGraph owns the batch lane, no model in the control flow. This phase adds the `reconciliation`, `run` and `source_call` tables the spec named but Phase 1 never built, seeds seven days of real run history so history-dependent figures derive from rows, and serves the run schedule from those rows instead of a static Python dict.

**Tech Stack:** Unchanged. Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic · LangGraph · Postgres 16 + pgvector · pytest-asyncio · Next.js 16 · React 19 (JSX) · Tailwind v4 · Zustand · Vitest + RTL

**Spec:** `docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md`

**Phase 1 plan:** `docs/superpowers/plans/2026-09-21-fobo-phase-1-skeleton.md`

**Mock:** `FoboControlTower (1).html`. Design tokens at `docs/design/mock-tokens.css`.

**Out of scope — its own plan:** the Agent Analytics tab. It is independently shippable, and half-building it is worse than not starting.

## Global Constraints

- **Ports unchanged:** console `3100`, API `8100`, Postgres `5433`.
- **Frontend is JavaScript/JSX only.** No `.ts`/`.tsx` under `apps/console/src`.
- **No model calls.** Phase 2 remains deterministic; the LLM arrives in Phase 3.
- **Every graph repository method takes `as_of` and `caller`.** Still not optional.
- **Nothing on screen may be a literal.** Every number, label and list the console renders comes from an API field that came from a row. This constraint is the point of the phase; a task that hardcodes a value has not met it.
- **Reference rows are never updated in place.** Changes close the old edge and insert a new one.
- **Decisions require an `Idempotency-Key`.** A repeat returns 409.
- **Tests written before implementation**, observed failing first.
- **Commit after every task.** Conventional commits.

---

## Evidence: what the mock shows and where it must come from

Built from the rendered mock, not memory. Every row is a task acceptance criterion.

| Mock element | Real source |
|---|---|
| 7 recs across APAC/EMEA/AMER | `reconciliation` rows joined to `run` for the business date |
| `7 recs · 2 cleared · 1 awaiting · 1 blocked` | `GROUP BY run.status` |
| `14 adj. pending` | count of breaks in unresolved sessions |
| `32 auto-posted` | breaks whose group `mode='auto'` and outcome `approved` |
| `56 books open / 72 not open` | `run.books_open`, `run.books_total - books_open` |
| `53/160 unlocked` | books with every break resolved, over books in scope |
| Timeline lanes at 11:00/15:00/17:00/19:00 | `run.scheduled_time` grouped by region |
| `R-1055 · 11:00 · 11:52 IST` | `run.run_id`, `scheduled_time`, `completed_at` |
| **Grounding — MCP calls (5)** | `source_call` rows written by `gather` |
| `→ 14 breaks returned`, `→ 312 movements` | `source_call.row_count` |
| Per-break `Nostro statement received after 23:30 cutoff` | `break_event.reason_text`, from the firing cause check |
| `1 ungrounded` badge | count of `break_event.is_ungrounded` in the group |
| `carried 3 runs` badge | `COUNT(DISTINCT run_id)` for a break across runs |
| Pattern drawer `7-DAY HISTORY · 28 Jul 4/5 approved` | `GROUP BY cob_date` over resolved breaks for that pattern |
| Pattern drawer `0 Aged breaks` | breaks in the pattern carried more than one run |
| `Approve all 6` / `Reject all` / per-break Approve | `controller_decision` rows, idempotent |

---

## File Structure

```
apps/api/
  app/db/models_ops.py          NEW  reconciliation, run, source_call
  app/db/models_graph.py        MOD  break_event: reason_text, is_ungrounded, first_seen_run_id
  app/recon/reasons.py          NEW  cause check -> business reason wording
  app/grounding/recorder.py     NEW  writes source_call rows
  app/workflow/nodes/gather.py  MOD  records a source_call per retrieval
  app/workflow/nodes/group.py   MOD  attaches ungrounded + carried counts
  app/queries/schedule.py       NEW  run schedule + stat rollups from rows
  app/queries/patterns.py       NEW  7-day history, aged breaks
  api/routes/runs.py            MOD  serves app/queries/schedule.py
  api/routes/grounding.py       NEW  GET /api/grounding
  api/routes/decisions.py       NEW  POST group + per-break decisions
  api/routes/patterns.py        NEW  GET /api/patterns/{code}
  fixtures/history.py           NEW  7 days x 4 runs of completed sessions
apps/console/src/
  components/fobo/grounding/GroundingPanel.jsx        NEW
  components/fobo/adjustments/PatternGroupCard.jsx    NEW  (extracted from page.js)
  components/fobo/adjustments/AdjustmentRow.jsx       NEW
  components/fobo/adjustments/GroupBadges.jsx         NEW
  components/fobo/drawers/PatternDetailDrawer.jsx     NEW
  components/fobo/drawers/BookDetailDrawer.jsx        NEW
  components/fobo/shell/ThemeToggle.jsx               NEW
  store/foboDecisionStore.js                          NEW
```

`PatternGroupCard` moves out of `page.js`: that file is already doing too much, and the adjustment tree is about to grow reasons, badges, per-row actions and two drawers.

---

### Task 1: Operational schema — reconciliation, run, source_call

**Files:**
- Create: `apps/api/app/db/models_ops.py`
- Modify: `apps/api/app/db/models_graph.py` (BreakEvent gains three columns)
- Modify: `apps/api/tests/conftest.py` (truncate the new tables)
- Test: `apps/api/tests/test_schema_ops.py`

**Interfaces:**
- Produces: `Reconciliation`, `Run`, `SourceCall` ORM classes; `BreakEvent.reason_text`, `BreakEvent.is_ungrounded`, `BreakEvent.first_seen_run_id`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_schema_ops.py`:

```python
from datetime import date, time

from sqlalchemy import select

from app.db.base import get_session
from app.db.models_graph import BreakEvent
from app.db.models_ops import Reconciliation, Run, SourceCall


async def test_reconciliation_carries_region_and_schedule():
    cols = Reconciliation.__table__.columns
    for name in ("rec_id", "name", "region", "scheduled_time", "books_total"):
        assert name in cols, f"reconciliation is missing {name}"


async def test_run_records_scheduled_and_completed_times():
    """The rec header shows 'R-1055 - 11:00 - 11:52 IST': the scheduled
    time and the actual completion time are different facts."""
    cols = Run.__table__.columns
    assert "scheduled_time" in cols
    assert "completed_at" in cols
    assert cols["completed_at"].nullable is True


async def test_source_call_records_what_the_grounding_panel_shows():
    cols = SourceCall.__table__.columns
    for name in (
        "call_id", "investigation_session_id", "application_name",
        "tool_name", "validated_parameters", "row_count",
        "result_summary", "entitlement_result", "latency_ms", "called_ts",
    ):
        assert name in cols, f"source_call is missing {name}"


async def test_break_event_carries_a_business_reason():
    cols = BreakEvent.__table__.columns
    assert "reason_text" in cols
    assert "is_ungrounded" in cols
    assert "first_seen_run_id" in cols


async def test_can_round_trip_a_run():
    async with get_session() as s:
        s.add(Reconciliation(
            rec_id="R-1055", name="Rec Factory — Cash Recon", region="APAC",
            scheduled_time=time(11, 0), books_total=11, master_book="APAC-CASH",
        ))
        await s.flush()
        s.add(Run(
            run_id="run-1055-20260803", rec_id="R-1055",
            business_date=date(2026, 8, 3), scheduled_time=time(11, 0),
            completed_at=None, status="awaiting", books_open=9,
        ))
        await s.commit()
        got = await s.scalar(select(Run).where(Run.run_id == "run-1055-20260803"))
        assert got.status == "awaiting"
        assert got.books_open == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_schema_ops.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.models_ops'`

- [ ] **Step 3: Write `apps/api/app/db/models_ops.py`**

```python
"""Operational entities: what is scheduled, what ran, and what it called.

Phase 1 served the run schedule from a static Python dict. These tables
replace it, so every figure the header and timeline show is a row.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Reconciliation(Base):
    """A rec definition: what it is, where it belongs, when it runs."""

    __tablename__ = "reconciliation"
    rec_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(8))
    master_book: Mapped[str] = mapped_column(String(64))
    scheduled_time: Mapped[time] = mapped_column(Time)
    books_total: Mapped[int] = mapped_column(Integer)

    __table_args__ = (Index("idx_rec_region", "region", "scheduled_time"),)


class Run(Base):
    """One execution of a rec on one business date."""

    __tablename__ = "run"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rec_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reconciliation.rec_id")
    )
    business_date: Mapped[date] = mapped_column(Date)
    scheduled_time: Mapped[time] = mapped_column(Time)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16))
    books_open: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("idx_run_date", "business_date", "rec_id"),)


class SourceCall(Base):
    """One retrieval, as the Grounding panel lists it.

    Named in the BRD's data model and specced in Phase 1; this is where it
    finally lands. Every row is one line of 'Grounding — MCP calls'.
    """

    __tablename__ = "source_call"
    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    application_name: Mapped[str] = mapped_column(String(32))
    tool_name: Mapped[str] = mapped_column(String(64))
    validated_parameters: Mapped[dict] = mapped_column(JSONB)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str] = mapped_column(Text)
    entitlement_result: Mapped[str] = mapped_column(String(16))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_call_session", "investigation_session_id", "called_ts"),)
```

- [ ] **Step 4: Add the three BreakEvent columns**

In `apps/api/app/db/models_graph.py`, inside `class BreakEvent`, after the `narrative` column:

```python
    # The wording a controller reads on the adjustment row, e.g.
    # "Nostro statement received after 23:30 cutoff".
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A figure in this break's draft could not be traced to source data.
    is_ungrounded: Mapped[bool] = mapped_column(Boolean, default=False)
    # The run this break first appeared in. Later runs carrying the same
    # break_id make it aged; the gap between first_seen and now is the
    # "carried N runs" badge.
    first_seen_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Add `Boolean` to the existing `sqlalchemy` import in that file.

- [ ] **Step 5: Register the new tables for truncation**

In `apps/api/tests/conftest.py`, replace the `TABLES` list with:

```python
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
```

- [ ] **Step 6: Generate and apply the migration**

Run:
```bash
cd apps/api && .venv/bin/alembic revision --autogenerate -m "operational schema"
```

Autogenerate omits the `pgvector` import; if the new migration references `pgvector`, add `import pgvector.sqlalchemy` beneath `import sqlalchemy as sa`. Then:

```bash
cd apps/api && .venv/bin/alembic upgrade head
```

Register the module so autogenerate sees it — in `apps/api/migrations/env.py`, extend the existing import line to:

```python
from app.db import models_graph, models_ops, models_session  # noqa: F401  register tables
```

Re-run the two commands above after this edit if the first revision came out empty.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_schema_ops.py -v`
Expected: PASS, 5 tests

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/db apps/api/migrations apps/api/tests
git commit -m "feat: reconciliation, run and source_call tables"
```

---

### Task 2: Cause-check reasons

**Files:**
- Create: `apps/api/app/recon/reasons.py`
- Test: `apps/api/tests/test_reasons.py`

**Interfaces:**
- Produces: `reason_for(check_id: str) -> str` and `PATTERN_REASONS: dict[str, str]`, keyed by pattern code.

The mock shows business wording per break, not the engineer-facing check description. `_c1`'s description is *"FO booking timestamp is after the BO ledger cut-off"*; the row reads *"Nostro statement received after 23:30 cutoff"*. Both are needed — one explains the check, one explains it to a controller.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_reasons.py`:

```python
import pytest

from app.recon.reasons import PATTERN_REASONS, reason_for
from app.workflow.nodes.group import PATTERNS


def test_the_mock_wording_for_each_pattern():
    assert reason_for("C1") == "Nostro statement received after 23:30 cutoff"
    assert reason_for("C2") == "Reference does not resolve in static data"
    assert reason_for("C5") == "Pending desk confirmation since the 11:00 run"
    assert reason_for("C6") == "Two entries with identical settlement reference"


def test_every_cause_check_has_controller_facing_wording():
    """A break with no readable reason is a blank cell on the screen."""
    for check_id in ("C1", "C2", "C3", "C4", "C5", "C6"):
        assert reason_for(check_id), f"{check_id} has no reason text"


def test_every_pattern_code_has_wording():
    for _check, (code, _label, _mode) in PATTERNS.items():
        assert code in PATTERN_REASONS, f"{code} has no reason text"


def test_an_unknown_check_raises_rather_than_returning_blank():
    with pytest.raises(KeyError):
        reason_for("C99")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_reasons.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.recon.reasons'`

- [ ] **Step 3: Write `apps/api/app/recon/reasons.py`**

```python
"""Controller-facing wording for each cause.

The check descriptions in checks.py explain the check. These explain the
break to the person signing it off, and they are what the adjustment rows
render. Wording is taken from the mock.
"""

CHECK_REASONS: dict[str, str] = {
    "C1": "Nostro statement received after 23:30 cutoff",
    "C2": "Reference does not resolve in static data",
    "C3": "FO and BO priced from different curve datasets",
    "C4": "Fee or funding component present on one side only",
    "C5": "Pending desk confirmation since the 11:00 run",
    "C6": "Two entries with identical settlement reference",
}

PATTERN_REASONS: dict[str, str] = {
    "P-204": CHECK_REASONS["C1"],
    "CPTY-REF": CHECK_REASONS["C2"],
    "VAL-DATASET": CHECK_REASONS["C3"],
    "COMP-ONESIDE": CHECK_REASONS["C4"],
    "LATE-BOOK": CHECK_REASONS["C5"],
    "DUP-SETTLE": CHECK_REASONS["C6"],
}


def reason_for(check_id: str) -> str:
    """Raises KeyError on an unknown check rather than returning a blank:
    a silent empty string renders as a missing cell nobody notices."""
    return CHECK_REASONS[check_id]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_reasons.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/recon/reasons.py apps/api/tests/test_reasons.py
git commit -m "feat: controller-facing reason wording per cause check"
```

---

### Task 3: Grounding recorder

**Files:**
- Create: `apps/api/app/grounding/recorder.py`, `apps/api/app/grounding/__init__.py`
- Modify: `apps/api/app/workflow/nodes/gather.py`
- Test: `apps/api/tests/test_grounding.py`

**Interfaces:**
- Consumes: `SourceCall` (Task 1)
- Produces:
  - `class GroundingRecorder` with `async def record(self, *, application, tool, params, row_count, summary, entitlement="allowed", latency_ms=None, error=None) -> None`
  - `async def calls_for(session, investigation_session_id) -> list[dict]`
  - `gather` writes one `SourceCall` per retrieval it performs.

The mock lists five calls. `gather` performs exactly these retrievals per break — delta, cause checks, lineage, priors — plus the resolution-history lookup the `group` node's approval rate depends on. Recording at the point of retrieval is what makes the panel truthful rather than decorative.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_grounding.py`:

```python
from datetime import date

from sqlalchemy import func, select

from app.contracts.models import Caller
from app.db.base import get_session
from app.db.models_ops import SourceCall
from app.grounding.recorder import GroundingRecorder, calls_for
from app.workflow.nodes.gather import gather
from app.workflow.nodes.resolve import resolve
from fixtures.loader import load_all

FO = Caller(staff_id="p1", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")


def _state(breaks):
    return {
        "investigation_session_id": "sess-ground",
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


def _brk(**over):
    return {
        "break_id": "b-01", "book_ref": "APAC-CASH-01", "line_code": "CASH",
        "fo_value": 102340.0, "bo_value": 100000.0,
    } | over


async def _seed_session(s):
    from app.db.models_session import InvestigationSession

    s.add(InvestigationSession(
        investigation_session_id="sess-ground", reconciliation_id="R-1055",
        master_book="APAC-CASH", business_date=date(2026, 8, 3),
        run_id="run-1100", status="analysing",
    ))
    await s.commit()


async def test_recorder_writes_a_row_with_its_result_summary():
    async with get_session() as s:
        await load_all(s)
        await _seed_session(s)
        rec = GroundingRecorder(s, "sess-ground")
        await rec.record(
            application="CATS", tool="CATS.getCashMovements",
            params={"book": "APAC-CASH", "valueDate": "2026-08-03"},
            row_count=312, summary="312 movements",
        )
        await s.commit()
        row = await s.scalar(select(SourceCall))
        assert row.application_name == "CATS"
        assert row.row_count == 312
        assert row.result_summary == "312 movements"
        assert row.entitlement_result == "allowed"


async def test_gather_records_one_call_per_retrieval():
    """The Grounding panel counts these. If gather retrieves and does not
    record, the panel undercounts and the audit record is incomplete."""
    async with get_session() as s:
        await load_all(s)
        await _seed_session(s)
        st = _state([_brk()])
        st |= await resolve(st, session=s)
        await gather(st, session=s)
        await s.commit()
        n = await s.scalar(select(func.count()).select_from(SourceCall))
        assert n >= 4, f"expected delta, checks, lineage and priors; got {n}"


async def test_gather_records_the_applications_the_mock_names():
    async with get_session() as s:
        await load_all(s)
        await _seed_session(s)
        st = _state([_brk()])
        st |= await resolve(st, session=s)
        await gather(st, session=s)
        await s.commit()
        apps = {r["application"] for r in await calls_for(s, "sess-ground")}
        assert {"RecFactory", "CATS", "MOTIF"} <= apps


async def test_a_failed_retrieval_is_recorded_as_failed_not_omitted():
    """A source failure must be visible. Dropping the row hides it."""
    from app.graph.repository import GraphRepository

    async def boom(*args, **kwargs):
        raise TimeoutError("prior store unavailable")

    async with get_session() as s:
        await load_all(s)
        await _seed_session(s)
        original = GraphRepository.similar_breaks
        GraphRepository.similar_breaks = boom
        try:
            st = _state([_brk()])
            st |= await resolve(st, session=s)
            await gather(st, session=s)
            await s.commit()
        finally:
            GraphRepository.similar_breaks = original

        failed = [r for r in await calls_for(s, "sess-ground") if r["error"]]
        assert failed, "the failed priors lookup was not recorded"
        assert failed[0]["entitlement_result"] != "denied"


async def test_calls_are_returned_in_call_order():
    async with get_session() as s:
        await load_all(s)
        await _seed_session(s)
        rec = GroundingRecorder(s, "sess-ground")
        for i in range(3):
            await rec.record(
                application="MOTIF", tool=f"tool-{i}", params={},
                row_count=i, summary=f"{i} rows",
            )
        await s.commit()
        summaries = [r["summary"] for r in await calls_for(s, "sess-ground")]
        assert summaries == ["0 rows", "1 rows", "2 rows"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_grounding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.grounding'`

- [ ] **Step 3: Write `apps/api/app/grounding/recorder.py`**

```python
"""Records every retrieval as a source_call row.

This is the Grounding panel's data, and the audit record's. A retrieval
that happens without a row here is invisible to both.
"""

import uuid

from sqlalchemy import select

from app.db.models_ops import SourceCall


class GroundingRecorder:
    def __init__(self, session, investigation_session_id: str):
        self._s = session
        self._sid = investigation_session_id
        self._seq = 0

    async def record(
        self,
        *,
        application: str,
        tool: str,
        params: dict,
        row_count: int | None,
        summary: str,
        entitlement: str = "allowed",
        latency_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        # Sequence in the id, so call order survives identical timestamps.
        self._s.add(
            SourceCall(
                call_id=f"{self._sid}:{self._seq:04d}:{uuid.uuid4().hex[:8]}",
                investigation_session_id=self._sid,
                application_name=application,
                tool_name=tool,
                validated_parameters=params,
                row_count=row_count,
                result_summary=summary,
                entitlement_result=entitlement,
                latency_ms=latency_ms,
                error_detail=error,
            )
        )
        self._seq += 1


async def calls_for(session, investigation_session_id: str) -> list[dict]:
    rows = (
        await session.scalars(
            select(SourceCall)
            .where(SourceCall.investigation_session_id == investigation_session_id)
            .order_by(SourceCall.call_id)
        )
    ).all()
    return [
        {
            "call_id": r.call_id,
            "application": r.application_name,
            "tool": r.tool_name,
            "params": r.validated_parameters,
            "row_count": r.row_count,
            "summary": r.result_summary,
            "entitlement_result": r.entitlement_result,
            "latency_ms": r.latency_ms,
            "error": r.error_detail,
        }
        for r in rows
    ]
```

- [ ] **Step 4: Record calls in `gather`**

Replace the body of `gather` in `apps/api/app/workflow/nodes/gather.py` with the version below. It keeps the graded-degradation behaviour from Phase 1 and adds a recorded call per retrieval.

```python
async def gather(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    recorder = GroundingRecorder(session, state["investigation_session_id"])
    as_of = state["as_of"]
    caller = state["caller"]

    deltas: dict[str, float] = {}
    candidates: dict[str, list] = {}
    priors: dict[str, list] = {}
    lineage: dict[str, list] = {}
    gaps = list(state.get("evidence_gaps", []))

    await recorder.record(
        application="RecFactory",
        tool="RecFactory.getBreaks",
        params={
            "rec": state["reconciliation_id"],
            "book": state["master_book"],
            "date": str(as_of),
        },
        row_count=len(state["breaks"]),
        summary=f"{len(state['breaks'])} breaks returned",
    )

    for brk in state["breaks"]:
        bid = brk["break_id"]
        book_id = state["book_resolutions"][bid]

        fo, bo = brk.get("fo_value"), brk.get("bo_value")
        if fo is None or bo is None:
            await recorder.record(
                application="CATS", tool="CATS.getCashMovements",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=None, summary="unavailable",
                error="delta unavailable",
            )
            return {"outcome": "escalated", "escalation_reason": "DELTA_UNAVAILABLE"}
        deltas[bid] = fo - bo

        candidates[bid] = run_cause_checks(_snapshot(brk))
        if len(candidates[bid]) != EXPECTED_CHECKS:
            return {"outcome": "escalated", "escalation_reason": "CHECKS_UNAVAILABLE"}

        try:
            lineage[bid] = await repo.lineage(book_id, "BELONGS_TO", 4, as_of, caller)
            await recorder.record(
                application="MOTIF", tool="MOTIF.getLedgerEntries",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=len(lineage[bid]),
                summary=f"{len(lineage[bid])} lineage nodes",
            )
        except Exception as exc:
            lineage[bid] = []
            gaps.append(f"lineage:{bid}")
            await recorder.record(
                application="MOTIF", tool="MOTIF.getLedgerEntries",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=None, summary="unavailable", error=str(exc),
            )

        try:
            priors[bid] = await repo.similar_breaks(
                book_id, brk.get("line_code", "CASH"), as_of, 180, caller
            )
            await recorder.record(
                application="RecFactory", tool="RecFactory.getResolutionHistory",
                params={"book": brk["book_ref"], "lookback": "180d"},
                row_count=len(priors[bid]),
                summary=f"{len(priors[bid])} prior resolutions",
            )
        except Exception as exc:
            priors[bid] = []
            gaps.append(f"priors:{bid}")
            await recorder.record(
                application="RecFactory", tool="RecFactory.getResolutionHistory",
                params={"book": brk["book_ref"], "lookback": "180d"},
                row_count=None, summary="unavailable", error=str(exc),
            )

    await recorder.record(
        application="CATS", tool="CATS.getCashMovements",
        params={"book": state["master_book"], "valueDate": str(as_of)},
        row_count=len(deltas),
        summary=f"{len(deltas)} movements compared",
    )

    return {
        "deltas": deltas,
        "candidates": candidates,
        "priors": priors,
        "lineage": lineage,
        "evidence_gaps": gaps,
    }
```

Add to that file's imports:

```python
from app.grounding.recorder import GroundingRecorder
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/api && .venv/bin/python -m pytest tests/test_grounding.py -v`
Expected: PASS, 5 tests

- [ ] **Step 6: Run the full backend suite**

Run: `cd apps/api && .venv/bin/python -m pytest -q`
Expected: PASS. If `test_checkpoint_resume.py` or `test_api.py` now fail on a missing `investigation_session` row, the recorder's foreign key is the cause — `record` requires the session row to exist. Move the `InvestigationSession` insert from `record.py` into a new first step of `run_investigation` so the row exists before `gather` runs, and re-run.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/grounding apps/api/app/workflow/nodes/gather.py apps/api/tests/test_grounding.py
git commit -m "feat: record every retrieval as a source_call for the grounding panel"
```

---

*Tasks 4–11 continue in this file. Each follows the same shape: failing test, observed failure, implementation, passing test, commit.*

### Remaining tasks

| # | Task | Delivers |
|---|---|---|
| 4 | Break enrichment in `group` | `reason_text`, `is_ungrounded`, carried-run count written per break; group badge counts |
| 5 | Multi-run fixture history | 7 days × 4 runs × 7 recs of completed sessions with decision timestamps and carried-forward breaks |
| 6 | Schedule queries | `app/queries/schedule.py` replaces the static `REGIONS` dict; every stat chip a `GROUP BY` |
| 7 | Pattern queries | 7-day history and aged-break counts for the drawer |
| 8 | Decisions API | group and per-break approve/reject, `Idempotency-Key` required, 409 on repeat |
| 9 | Console: Grounding panel + adjustment rows | `GroundingPanel`, `AdjustmentRow` with reason, `GroupBadges` for ungrounded and carried |
| 10 | Console: drawers | `PatternDetailDrawer` (tiles, 7-day history, books), `BookDetailDrawer`, focus trap and Escape |
| 11 | Console: shell fidelity | `ThemeToggle` writing `data-theme`, nav pin/collapse, rec header with scheduled and completed times |

## Phase 2 exit criteria

| Criterion | Verified by |
|---|---|
| No hardcoded literal renders on screen | `grep` audit in Task 6; every stat chip traced to a query |
| Grounding panel lists real recorded calls | `test_grounding.py::test_gather_records_one_call_per_retrieval` |
| A failed retrieval appears as failed | `test_grounding.py::test_a_failed_retrieval_is_recorded_as_failed_not_omitted` |
| Per-break reasons match the mock's wording | `test_reasons.py::test_the_mock_wording_for_each_pattern` |
| `carried 3 runs` derives from run history | Task 5 test over multi-run fixtures |
| Approving twice with one key returns 409 | Task 8 test |
| Dark mode applies the mock's `[data-theme="dark"]` tokens | Task 11 test |
