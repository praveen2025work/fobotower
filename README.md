# Agent One Finance — governed AI for Finance

Agent One Finance is the platform Finance teams run their AI-assisted case work on: breaks,
reconciliations, variance commentary, accruals, report validation, control
testing. Each use case is a **capability**: configuration over the team's own
systems (MCP connectors), run by LangGraph, governed end to end and worked in
one console. Rules come first, then the model, then a person; named people
decide within their authority; only approved outcomes are written back.

**FOBO is one use case.** Front-office vs back-office break investigation for
the Prime and Rates desks was the first capability, and the original FOBO
investigation console still runs beside Agent One Finance (below). On Agent One Finance it is the
`break.investigation` capability with its playbook as configuration.

| Finance area | Running on Agent One Finance today |
|---|---|
| Product control | FOBO break investigation (Prime, Rates) |
| Financial control | Reconciliation investigation, month-end accruals, control operating test |
| Financial reporting | P&L variance commentary, report validation |
| Treasury and payments operations | Payment exceptions |

The same platform runs work beyond Finance too (complaint handling is the
example in this repo).

- **Renamed from Helix:** [`docs/agent-one-finance/renaming.md`](docs/agent-one-finance/renaming.md) — the old → new names for an office deployment <!-- aof-convert: keep -->
- **Bringing AOF into the office repos (aos-frontend, aos-backend):** [`docs/agent-one-finance/office/conversion-guide.md`](docs/agent-one-finance/office/conversion-guide.md) — one guide, one converter, one sync tool
- **Start here:** [`docs/agent-one-finance/README.md`](docs/agent-one-finance/README.md) — what runs where, how to run it, the guides
- **Platform overview:** [`docs/agent-one-finance/platform-overview.md`](docs/agent-one-finance/platform-overview.md) · **pitch page:** [`docs/agent-one-finance/pitch/agent-one-finance-pitch.html`](docs/agent-one-finance/pitch/agent-one-finance-pitch.html) (open in a browser)
- **Run Agent One Finance locally:** API on :8300 (`uvicorn agent_one_finance.web.main:app`), console on :5180 (`apps/web`, `npm run dev`); see the [developer guide](docs/agent-one-finance/guide/developer-guide.md#3-run-it-locally)

## Use case: the FOBO investigation console (original app)

The first use case, built before the platform. A controller opens a completed
reconciliation analysis, interrogates it in business language, pulls missing
evidence from owning source systems, and records a governed decision with a
replayable audit trail. Built to AgentOne component conventions but runs
standalone.

- **Learning guide:** [`docs/learning/agentic-systems-primer.html`](docs/learning/agentic-systems-primer.html) — LLMs, agents, MCP, LangGraph and knowledge graphs explained from first principles (open in a browser)
- **Deployment:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — running it on a shared demo or UAT server
- **Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — what each folder is, who uses it, and where to change what
- **Design:** [`docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md`](docs/superpowers/specs/2026-09-21-fobo-investigation-console-design.md)
- **Phase 1 plan:** [`docs/superpowers/plans/2026-09-21-fobo-phase-1-skeleton.md`](docs/superpowers/plans/2026-09-21-fobo-phase-1-skeleton.md)


### Status

| Phase | Scope | State |
|---|---|---|
| 1 | Contracts, schema, fixtures, LangGraph through the review interrupt, console shell | **Done** — 13 tasks, 105 tests |
| 2 | Analysis panel, grounding list, pattern-grouped adjustments, idempotent decisions | Not started |
| 3 | MCP tool groups, entitlement gate, chat drawer, rules R1–R7, `revise` | Not started |
| 4 | MBR + Trade Store, file ingestion, paging, analytics, evals | Not started |

### Prerequisites

- Docker (for Postgres 16 + pgvector)
- Python 3.12 — the venv is already created at `apps/backend/.venv`
- Node 20+ — console dependencies are already installed

### Testing

#### 1. Start the database

```bash
docker compose up -d postgres
```

#### 2. Apply migrations

```bash
cd apps/backend && .venv/bin/alembic upgrade head
```

After pulling this change, run the same command — it applies the migration
that added workflow versioning.

Investigations opened before the 2026-09-26 naming cleanup checkpointed
their state under the old `app.contracts.models` path; `fobo/contracts/models.py`
registers that name as a compatibility alias, so those older checkpoints
still load with real typed objects — no reset of the dev database needed.

#### 3. Run the suite

```bash
cd apps/backend && .venv/bin/python -m pytest -v
```

388 tests. They are re-runnable: `tests/conftest.py` truncates every table
before each test.

#### 4. See an investigation run

```bash
cd apps/backend && .venv/bin/python scripts/demo_investigation.py
```

Loads seed data, runs the workflow to the human interrupt, prints the drafted
analysis and pattern groups exactly as a controller would see them, then
resumes with per-group approvals and reports the recorded outcome.

#### 5. Run the whole thing

Three terminals:

```bash
docker compose up -d postgres
```

```bash
cd apps/backend && FOBO_ENV=dev .venv/bin/uvicorn fobo.web.main:app --port 8100 --reload
```

`FOBO_ENV=dev` enables the **Act as** switch in the console header, so a
second person can approve a workflow draft.

```bash
cd apps/console && npm run dev
```

Then open **http://localhost:3100** for the Agent One Finance console, the finalized UI
(Agent One Finance Pilot V1). (`/fobo` still works — it redirects to `/` for old
bookmarks.)

#### Running on Windows

Prerequisites: **Python 3.12**, **Node 20+**, **Git**, and a container runtime
that runs `docker compose` (Docker Desktop with WSL 2, Rancher Desktop or
Podman Desktop). The virtualenv and `node_modules` are not in the repo, so the
first run creates them. Commands are for PowerShell, from the repo root.

One-time setup:

```powershell
docker compose up -d postgres
cd apps\backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\alembic upgrade head
cd ..\console
npm install
```

Then two terminals:

```powershell
cd apps\backend
$env:FOBO_ENV = "dev"
.venv\Scripts\uvicorn fobo.web.main:app --port 8100 --reload --loop asyncio:SelectorEventLoop
```

```powershell
cd apps\console
npm run dev
```

`--loop asyncio:SelectorEventLoop` is required on Windows: the LangGraph
checkpointer uses psycopg, which cannot run on Windows' default event loop.
The CLIs, scripts and tests pick the right loop on their own
(`fobo/__init__.py`). Everything else — tests, scripts, the reset command —
works as above with `.venv\Scripts\` in place of `.venv/bin/`.

#### The FOBO console

Everything on screen is read from the API; the browser generates nothing.

| On screen | Comes from |
|---|---|
| Recs, Ready events, master-book readiness, book states | `reconciliation` and `run` rows (`seed_data/catalogue.py` seeds them) |
| Drafted adjustments, verdicts, fixes | the LangGraph investigation's checkpoint and the playbook |
| Analysis (what, why, action, risk) | the draft node, plus grounding and carry flags |
| MCP data (N) | `source_call` rows, with the rows each tool returned |
| Agent One answers | `POST /api/recs/{id}/messages`: a deterministic intent router; anything it cannot answer goes to the reasoner (none by default) |
| Approve / Reject | `POST /api/recs/{id}/decisions`, double-confirmed, one idempotency key per decision |
| Notification bell | derived from runs and today's decisions |
| **Graph run** (session header) | `GET /api/recs/{id}/trace`: each LangGraph step from the checkpoints |

The whole board is one call: `GET /api/board`, which also opens (running, if
needed) each rec's investigation — the console never calls
`POST /api/recs/{id}/investigate` itself; that endpoint exists for
`scripts/run_investigation.py` and the e2e test to start a run directly.

To reset the scenario (undo every decision and question), clear the app tables
and checkpoints; the next request reseeds:

```bash
docker compose exec postgres psql -U fobo -d fobo -c "TRUNCATE session_message, source_call, controller_decision, pattern_group, evidence_item, analysis_version, investigation_session, break_embedding, break_event, edge, node, run, reconciliation, checkpoints, checkpoint_blobs, checkpoint_writes CASCADE"
```

#### 6. Console tests

```bash
cd apps/console && npm test
```

185 tests. No database needed — components are tested against props.

#### 7. End-to-end test

```bash
cd apps/console && npm run test:e2e
```

Runs the workflow end-to-end test against a fresh `fobo_e2e` database on
ports 8101/3101.

#### Starting completely clean

```bash
docker compose down -v && docker compose up -d postgres && sleep 8 && cd apps/backend && .venv/bin/alembic upgrade head && .venv/bin/python -m pytest -q
```

#### Recreating the venv

```bash
cd apps/backend && uv venv --python 3.12 && uv pip install -e ".[dev]"
```

### What the tests actually prove

These are the ones worth reading, not just running.

| Claim | Test |
|---|---|
| A run parks at the human interrupt and a **fresh process** resumes it to completion | `test_checkpoint_resume.py::test_state_survives_a_fresh_process_and_resumes_to_completion` |
| 14 breaks collapse into 4 decisions — the "decisions saved" metric | `test_step_group.py::test_group_sizes_match_the_mock` |
| The 88% approval rate is **derived** from 42 priors, not hard-coded | `test_step_group.py::test_p204_carries_the_historical_approval_rate` |
| A caller outside the entity scope cannot resolve a book, and cannot tell that from the book not existing | `test_repository.py::test_a_caller_outside_the_entity_scope_cannot_resolve` |
| A graph read returns the hierarchy in force on the COB date, not today's | `test_repository.py::test_as_of_returns_the_hierarchy_in_force_on_that_date` |
| The same snapshot produces byte-identical cause-check output | `test_cause_checks.py::test_is_deterministic` |
| A figure that does not trace to a computed delta is rejected | `test_steps_rank_draft_validate.py::test_validate_rejects_an_ungrounded_figure` |
| A failed priors lookup degrades and flags a gap — it does not fabricate | `test_steps_resolve_gather.py::test_gather_degrades_when_priors_are_unavailable` |
| An approved run stamps breaks so they become tomorrow's priors | `test_checkpoint_resume.py::test_an_approved_run_writes_tomorrows_priors` |

### The investigation playbook

The rules the orchestrator applies live in one file Product Control owns:

**[`config/playbook/fobo-cats-vs-motif.yaml`](config/playbook/fobo-cats-vs-motif.yaml)**

It holds the FO and BO validation tests, which test must run before another
can conclude, the evidence each needs, the break categories, the default
verdict for each category and side, escalation routes, and the policy
thresholds. It is loaded into the knowledge graph with an effective date.

```bash
cd apps/backend && .venv/bin/python -m fobo.playbook.cli validate
```

```bash
cd apps/backend && .venv/bin/python -m fobo.playbook.cli load
```

`validate` rejects the file if anything references a test, category, verdict
or team that is not defined — a typo fails the load instead of surfacing mid
investigation. It also refuses a playbook that would let a Front Office cause
post (R2).

Thresholds start as `null`. Rule P1: until one is set, any POST that depends
on it is flagged *requires controller confirmation*. Set a value and reload.

### The investigation workflow

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
(`apps/backend/fobo/investigation/step_registry.py`), which is how an order that cannot
work is caught before a run starts.

The **playbook** (`config/playbook/`) holds *what the rules are*; the
**workflow** (`config/workflow/`) holds *how the run executes*.

### Running without an LLM

```bash
cd apps/backend && .venv/bin/python scripts/run_investigation.py
```

With `FOBO_REASONER` unset, no model is called. Breaks the playbook can
settle get a verdict from it; breaks it cannot settle escalate to a human.
For each rec, the script prints its status, workflow version, and session
id, then the LangGraph step trace (`GET /api/recs/{id}/trace`) — one line
per step with its status and summary, the same sequence a controller sees
in the console's "Graph run" panel.

| `FOBO_REASONER` | Judgement-based breaks go to |
|---|---|
| unset / `none` | nobody — they escalate (no LLM) |
| `session_service` | the Agent SDK session service |
| `direct` | a direct Anthropic SDK call (local development) |

### Running with the stub agent harness

`apps/backend/scripts/stub_harness.py` stands in for the bank's agent harness.
It speaks the session contract
([`docs/integration/session-service-contract.md`](docs/integration/session-service-contract.md)),
reads each run's breaks through the backend's MCP server, and answers with a
fixed verdict. It is a demo double, not a reasoner. Three terminals, from the
repo root:

```bash
cd apps/backend && .venv/bin/uvicorn scripts.stub_harness:app --port 8200
```

```bash
cd apps/backend && FOBO_ENV=dev FOBO_REASONER=session_service FOBO_SESSION_SERVICE_URL=http://localhost:8200 FOBO_MCP_URL=http://localhost:8100/mcp .venv/bin/uvicorn fobo.web.main:app --port 8100
```

```bash
cd apps/console && npm run dev
```

Collateral (R-2048, one break left for the agent) runs on the board's first
read; its agent finding shows in the console, and the MCP data panel shows each
tool call the stub made (`application: agent`) plus one `agent.session` row.
FI Credit (R-2031, five breaks) is seeded as still running, so the board does
not start it; start it yourself and read its step trace:

```bash
curl -X POST localhost:8100/api/recs/R-2031/investigate && curl localhost:8100/api/recs/R-2031/trace
```

A rec that has already run keeps its result; use the reset command under
*The Agent One Finance console* first to see it run again.

`FOBO_MCP_URL` both turns on the MCP server at `/mcp` and is the URL the
harness is told to call. Each agent session gets its own MCP token; there is
no shared one. Three workflow settings govern a session:
`session_service.poll_interval_seconds` (5), `session_service.max_wait_seconds`
(900) and `reason.sample_breaks_per_pattern` (5).

Known limitation: investigations still start on the board's first read, so a
long agent session holds that board request open until it finishes.

### Known deviations from the mock

Both mocks state *"14 breaks across 9 … books"*, but their own adjustment rows
list twelve distinct books (`PRIME-MB-01`…`12`). The draft derives the count
from the data and reports 12. The mock's prose and its rows disagree; the rows
win.

Agent One Finance Pilot V1 invents some detail in the browser that the orchestrator has no
source for yet, so the port shows what the backend actually has instead:

- **Break legs.** The mock makes up trade references and times per leg. The
  API shows each break's CATS and MOTIF values as MB Rec reports them.
- **FAS posting preview, custody statement lookup, counterparty resolution.**
  No FAS, custody or reference-data MCP server is connected, so these calls
  are not made rather than faked.
- **Timestamps of new actions.** Decisions and questions carry the real clock
  (IST); the seeded business day is frozen at 03 Aug 2026.

### Ports

| Service | Port |
|---|---|
| Console | 3100 |
| API | 8100 |
| Postgres | 5433 |
| Stub agent harness | 8200 |
| Agent One Finance API | 8300 |
| Agent One Finance stub connectors over HTTP (optional) | 9101+ |

All offset from AgentOne's defaults so both stacks run simultaneously.
