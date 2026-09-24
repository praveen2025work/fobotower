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
| 1 | Contracts, schema, fixtures, LangGraph through the review interrupt, console shell | **Done** — 13 tasks, 105 tests |
| 2 | Analysis panel, grounding list, pattern-grouped adjustments, idempotent decisions | Not started |
| 3 | MCP tool groups, entitlement gate, chat drawer, rules R1–R7, `revise` | Not started |
| 4 | MBR + Trade Store, file ingestion, paging, analytics, evals | Not started |

## Prerequisites

- Docker (for Postgres 16 + pgvector)
- Python 3.12 — the venv is already created at `apps/api/.venv`
- Node 20+ — console dependencies are already installed

## Testing

### 1. Start the database

```bash
docker compose up -d postgres
```

### 2. Apply migrations

```bash
cd apps/api && .venv/bin/alembic upgrade head
```

After pulling this change, run the same command — it applies the migration
that added workflow versioning.

### 3. Run the suite

```bash
cd apps/api && .venv/bin/python -m pytest -v
```

80 tests. They are re-runnable: `tests/conftest.py` truncates every table
before each test.

### 4. See an investigation run

```bash
cd apps/api && .venv/bin/python scripts/demo_investigation.py
```

Loads fixtures, runs the workflow to the human interrupt, prints the drafted
analysis and pattern groups exactly as a controller would see them, then
resumes with per-group approvals and reports the recorded outcome.

### 5. Run the whole thing

Three terminals:

```bash
docker compose up -d postgres
```

```bash
cd apps/api && FOBO_ENV=dev .venv/bin/uvicorn api.main:app --port 8100 --reload
```

`FOBO_ENV=dev` enables the **Act as** switch in the console header, so a
second person can approve a workflow draft.

```bash
cd apps/console && npm run dev
```

Then open **http://localhost:3100/fobo** (or just **http://localhost:3100**)
for the Helix console, the finalized UI (Helix Pilot V1). The earlier console
is kept at **http://localhost:3100/classic** until it is retired.

### The Helix console

Everything on screen is read from the API; the browser generates nothing.

| On screen | Comes from |
|---|---|
| Recs, Ready events, master-book readiness, book states | `reconciliation` and `run` rows (`fixtures/catalogue.py` seeds them) |
| Drafted adjustments, verdicts, fixes | the LangGraph investigation's checkpoint and the playbook |
| Analysis (what, why, action, risk) | the draft node, plus grounding and carry flags |
| MCP data (N) | `source_call` rows, with the rows each tool returned |
| Agent One answers | `POST /api/helix/recs/{id}/messages`: a deterministic intent router; anything it cannot answer goes to the reasoner (none by default) |
| Approve / Reject | `POST /api/helix/recs/{id}/decisions`, double-confirmed, one idempotency key per decision |
| Notification bell | derived from runs and today's decisions |
| **Graph run** (session header) | `GET /api/recs/{id}/trace`: each LangGraph step from the checkpoints |

The whole board is one call: `GET /api/helix/board`.

To reset the scenario (undo every decision and question), clear the app tables
and checkpoints; the next request reseeds:

```bash
docker compose exec postgres psql -U fobo -d fobo -c "TRUNCATE session_message, source_call, controller_decision, pattern_group, evidence_item, analysis_version, investigation_session, break_embedding, break_event, edge, node, run, reconciliation, checkpoints, checkpoint_blobs, checkpoint_writes CASCADE"
```

### 6. Console tests

```bash
cd apps/console && npm test
```

25 tests. No database needed — components are tested against props.

### 7. End-to-end test

```bash
cd apps/console && npm run test:e2e
```

Runs the workflow end-to-end test against a fresh `fobo_e2e` database on
ports 8101/3101.

### Starting completely clean

```bash
docker compose down -v && docker compose up -d postgres && sleep 8 && cd apps/api && .venv/bin/alembic upgrade head && .venv/bin/python -m pytest -q
```

### Regenerating design tokens

```bash
cd apps/console && npm run build:tokens
```

Regenerates `src/styles/tokens.css` from `docs/design/mock-tokens.css`. The
source is extracted verbatim from the mock and is read-only; the build strips
its Google Fonts `@import`, because that file is inlined into `globals.css`
and an `@import` must precede every other rule. Fonts load via `next/font`.

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

## The investigation playbook

The rules the orchestrator applies live in one file Product Control owns:

**[`config/playbook/fobo-cats-vs-motif.yaml`](config/playbook/fobo-cats-vs-motif.yaml)**

It holds the FO and BO validation tests, which test must run before another
can conclude, the evidence each needs, the break categories, the default
verdict for each category and side, escalation routes, and the policy
thresholds. It is loaded into the knowledge graph with an effective date.

```bash
cd apps/api && .venv/bin/python -m app.playbook.cli validate
```

```bash
cd apps/api && .venv/bin/python -m app.playbook.cli load
```

`validate` rejects the file if anything references a test, category, verdict
or team that is not defined — a typo fails the load instead of surfacing mid
investigation. It also refuses a playbook that would let a Front Office cause
post (R2).

Thresholds start as `null`. Rule P1: until one is set, any POST that depends
on it is flagged *requires controller confirmation*. Set a value and reload.

## The investigation workflow

How an investigation *executes* — which steps run, in what order, where it
pauses for a person, and each step's settings — is a versioned, four-eyes
config, not a file you hand-edit and restart for:

The live workflow is stored in the database; the YAML file at
[`config/workflow/fobo-investigation.yaml`](config/workflow/fobo-investigation.yaml)
seeds version 1 and is the Download/Upload format.

In the console, open **Workflow**: the graph shows each step tagged Code /
Playbook + Reasoner / Template / Human, the pause before sign-off, and the
escalate branch. Click a step for its inputs, outputs and settings.

**New draft** → edit (rank on/off, order, pauses, settings, reasoner);
problems are listed as you edit → add a note → **Save draft**.

A different Product Control user opens the draft, reviews the changes
against the active version, and approves (two confirmations). New
investigations use it from then on; a run keeps the version it started with
(see "workflow vN" in the Graph run drawer).

`FOBO_REASONER` still overrides the reasoner for local development; the
Workflow tab shows a banner while it does.

| You can | You cannot |
|---|---|
| Drop the optional `rank` step | Remove `reason` — it applies the playbook and the verdict guards |
| Add a pause, e.g. before `reason`, to inspect a run | Remove `validate` — no ungrounded figure may reach a controller |
| Change lookback, depth, limits, retries, timeout | Remove `review`, or its pause — no decision without a person |
| Choose the reasoner: `none`, `session_service`, `direct` | Put a step before the step whose output it needs |

The validator refuses the right-hand column with a message naming the
problem. Each step declares what it needs and produces
(`apps/api/app/workflow/registry.py`), which is how an order that cannot
work is caught before a run starts.

The **playbook** (`config/playbook/`) holds *what the rules are*; the
**workflow** (`config/workflow/`) holds *how the run executes*.

## Running without an LLM

```bash
cd apps/api && .venv/bin/python scripts/run_investigation.py
```

With `FOBO_REASONER` unset, no model is called. Breaks the playbook can
settle get a verdict from it; breaks it cannot settle escalate to a human.
The report shows the deterministic share per rec, which is the
orchestrator's headline figure.

| `FOBO_REASONER` | Judgement-based breaks go to |
|---|---|
| unset / `none` | nobody — they escalate (no LLM) |
| `session_service` | the Agent SDK session service |
| `direct` | a direct Anthropic SDK call (local development) |

## Known deviations from the mock

Both mocks state *"14 breaks across 9 … books"*, but their own adjustment rows
list twelve distinct books (`PRIME-MB-01`…`12`). The draft derives the count
from the data and reports 12. The mock's prose and its rows disagree; the rows
win.

Helix Pilot V1 invents some detail in the browser that the orchestrator has no
source for yet, so the port shows what the backend actually has instead:

- **Break legs.** The mock makes up trade references and times per leg. The
  API shows each break's CATS and MOTIF values as MB Rec reports them.
- **FAS posting preview, custody statement lookup, counterparty resolution.**
  No FAS, custody or reference-data MCP server is connected, so these calls
  are not made rather than faked.
- **Timestamps of new actions.** Decisions and questions carry the real clock
  (IST); the seeded business day is frozen at 03 Aug 2026.

## Ports

| Service | Port |
|---|---|
| Console | 3100 |
| API | 8100 |
| Postgres | 5433 |

All offset from AgentOne's defaults so both stacks run simultaneously.
