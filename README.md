# FOBO Investigation Console

An AI-assisted reconciliation investigation system. A controller opens a
completed analysis, interrogates it in business language, pulls missing
evidence from owning source systems, and records a governed decision with a
replayable audit trail.

Built to AgentOne component conventions but runs standalone. Migration into
AgentOne is a separate, manual step.

- **Design:** [`docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md`](docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md)
- **Phase 1 plan:** [`docs/superpowers/plans/2026-09-21-fobo-phase-1-skeleton.md`](docs/superpowers/plans/2026-09-21-fobo-phase-1-skeleton.md)

## Status

| Phase | Scope | State |
|---|---|---|
| 1 | Contracts, schema, fixtures, LangGraph through the review interrupt, console shell | Backend done (Tasks 1–9). Console pending (Tasks 10–13) |
| 2 | Analysis panel, grounding list, pattern-grouped adjustments, idempotent decisions | Not started |
| 3 | MCP tool groups, entitlement gate, chat drawer, rules R1–R7, `revise` | Not started |
| 4 | MBR + Trade Store, file ingestion, paging, analytics, evals | Not started |

There is **no UI yet**. Everything below tests the backend.

## Prerequisites

- Docker (for Postgres 16 + pgvector)
- Python 3.12 — the venv is already created at `apps/api/.venv`

## Testing

### 1. Start the database

```bash
docker compose up -d postgres
```

### 2. Apply migrations

```bash
cd apps/api && .venv/bin/alembic upgrade head
```

### 3. Run the suite

```bash
cd apps/api && .venv/bin/python -m pytest -v
```

68 tests. They are re-runnable: `tests/conftest.py` truncates every table
before each test.

### 4. See an investigation run

```bash
cd apps/api && .venv/bin/python scripts/demo_investigation.py
```

Loads fixtures, runs the workflow to the human interrupt, prints the drafted
analysis and pattern groups exactly as a controller would see them, then
resumes with per-group approvals and reports the recorded outcome.

### Starting completely clean

```bash
docker compose down -v && docker compose up -d postgres && sleep 8 && cd apps/api && .venv/bin/alembic upgrade head && .venv/bin/python -m pytest -q
```

### Recreating the venv

```bash
cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]"
```

## What the tests actually prove

These are the ones worth reading, not just running.

| Claim | Test |
|---|---|
| A run parks at the human interrupt and a **fresh process** resumes it to completion | `test_checkpoint_resume.py::test_state_survives_a_fresh_process_and_resumes_to_completion` |
| 14 breaks collapse into 4 decisions — the "decisions saved" metric | `test_node_group.py::test_group_sizes_match_the_mock` |
| The 88% approval rate is **derived** from 42 priors, not hard-coded | `test_node_group.py::test_p204_carries_the_historical_approval_rate` |
| A caller outside the entity scope cannot resolve a book, and cannot tell that from the book not existing | `test_repository.py::test_a_caller_outside_the_entity_scope_cannot_resolve` |
| A graph read returns the hierarchy in force on the COB date, not today's | `test_repository.py::test_as_of_returns_the_hierarchy_in_force_on_that_date` |
| The same snapshot produces byte-identical cause-check output | `test_recon.py::test_is_deterministic` |
| A figure that does not trace to a computed delta is rejected | `test_nodes_rank_draft_validate.py::test_validate_rejects_an_ungrounded_figure` |
| A failed priors lookup degrades and flags a gap — it does not fabricate | `test_nodes_resolve_gather.py::test_gather_degrades_when_priors_are_unavailable` |
| An approved run stamps breaks so they become tomorrow's priors | `test_checkpoint_resume.py::test_an_approved_run_writes_tomorrows_priors` |

## Known deviations from the mock

`FoboControlTower (1).html` states *"14 breaks across 9 Cash books"*, but its
own adjustment rows list twelve distinct books (`APAC-CASH-01`…`12`). The
draft derives the count from the data and reports 12. The mock's prose and its
rows disagree; the rows win.

## Ports

| Service | Port |
|---|---|
| Console (pending) | 3100 |
| API (pending) | 8100 |
| Postgres | 5433 |

All offset from AgentOne's defaults so both stacks run simultaneously.
