# Architecture

A map of the repo: what each folder is, and who calls into it. For *why* the
code is laid out this way, see
[`docs/superpowers/specs/2026-09-26-codebase-naming-cleanup-design.md`](superpowers/specs/2026-09-26-codebase-naming-cleanup-design.md).

Main users lists the production importers (grep them for the full set).

## Request flow

```
console (apps/console/src)
  → GET /api/board                         fobo/web/routes/console.py
  → fobo/web/investigations.py             opens (runs, if needed) the checkpointed investigation
      → fobo/investigation/graph.py            the LangGraph investigation (steps/*)
          → fobo/knowledge_graph/*             books, desks, lineage (bitemporal)
          → fobo/cause_checks/*                the six deterministic cause checks
          → fobo/reasoning/*                   the model call, only for what the checks can't settle
  → fobo/console_views/*                   what the console shows, from the checkpoint + real rows
  → fobo/db/*                              SQLAlchemy models and the async session
```

A rec's investigation runs once, the first time anything asks for it — the
board's own first read through `fobo/web/investigations.py`, or explicitly
via `POST /api/recs/{id}/investigate` (used by `scripts/run_investigation.py`
and the e2e test, not by the console itself); every later read replays the
LangGraph checkpoint instead of re-running the graph. Everything the console
renders — the board, a rec's analysis, the chat drawer, the MCP call log, the
workflow trace — is read from the database; the browser computes nothing on
its own.

## apps/backend — the FastAPI service (package `fobo`)

Run with `uvicorn fobo.web.main:app`; tests from `apps/backend` with
`.venv/bin/python -m pytest`.

| Path | What it is | Main users |
|---|---|---|
| `fobo/web/` | HTTP layer: routes, auth, request-scoped dependencies | uvicorn entry point (`main.py`); the console over HTTP |
| `fobo/web/routes/console.py` | `GET /api/board`, `POST /api/recs/{id}/messages`, `POST /api/recs/{id}/decisions` | the console's board and rec detail (a rec's own view is read from `/api/board`, not fetched separately — see spec §5, amended during review) |
| `fobo/web/routes/investigations.py` | `POST /api/recs/{id}/investigate`, `GET /api/recs/{id}/trace` | `/trace` → the console (session header's graph run); `/investigate` → `scripts/run_investigation.py` and the e2e test only, not the console |
| `fobo/web/routes/workflow_config.py` | `/api/workflow/*`: versions, drafts, the compiled graph | the Workflow tab |
| `fobo/web/investigations.py` | open (run-if-needed) or read a rec's checkpointed investigation | `routes/console.py`, `routes/investigations.py`, `web/decisions.py`, `tests/test_decisions.py`, `tests/test_workflow_pinning.py` |
| `fobo/web/decisions.py` | apply a controller decision (idempotent on its key) | `routes/console.py`; `tests/test_decisions.py` (calls `apply_decision` directly) |
| `fobo/investigation/` | the LangGraph investigation itself: graph wiring, state, sessions, versioning | `fobo/web/*`, `scripts/*`, the CLI |
| `fobo/investigation/steps/` | one module per graph step (gather, group, rank, draft, validate, reason, escalate, resolve, record) | `graph.py`, wired in the order `step_registry.py` + the workflow config allow |
| `fobo/investigation/step_registry.py` | every step's declared inputs/outputs, so an invalid order is caught before a run starts | `investigation/graph.py` (`STEPS`, builds the graph), `investigation/graph_view.py` (`STEPS`, the Workflow tab's graph view), `investigation/cli.py`, `reports/trace.py`, `web/routes/workflow_config.py` (`catalogue`), `settings.py` (validation) |
| `fobo/investigation/settings.py` | reads and validates the workflow config (steps, order, pauses, settings) | `web/routes/workflow_config.py`, `reasoning/registry.py`, `reasoning/adapters/session_service.py`, `investigation/{graph,cli,yaml_io,graph_view,versions}.py`, `investigation/steps/{gather,reason,validate}.py` |
| `fobo/investigation/versions.py` | workflow versions: draft, diff, four-eyes approval, which version a run started with | `web/main.py` (`Invalid`, `VersionError` handler), `web/routes/console.py`, `web/routes/workflow_config.py`, `investigation/graph.py` |
| `fobo/investigation/graph_view.py` | the compiled graph and its decision logic, derived from code (not hand-typed) | the Workflow tab's graph view |
| `fobo/investigation/cli.py` | `python -m fobo.investigation.cli validate\|show` | Product Control (there is no CI in this repo) |
| `fobo/knowledge_graph/` | books, desks, ownership lineage — bitemporal (`as_of` + entitlement on every read) | `steps/resolve.py`, `steps/gather.py` (priors), `steps/reason.py`, `console_views/board.py`, `playbook/cli.py` |
| `fobo/cause_checks/` | the six deterministic cause checks (C1–C6) and their controller-facing wording | `steps/gather.py`, `steps/group.py` |
| `fobo/console_views/` | what the console shows for a rec: board row, detail, chat answers, activity feed, session view | `fobo/web/routes/console.py` |
| `fobo/reports/` | the board's hours-saved tile (`hours_saved.py`) and the execution trace (`trace.py`, from LangGraph checkpoints) | `hours_saved` → `routes/console.py`; `execution_trace` → `routes/investigations.py`; the console's Analytics panel |
| `fobo/reasoning/` | the reasoning port: routes judgement-based breaks to a model (or none), plus the verdict guards that graph code — not the model — enforces | `steps/reason.py`; `graph_view.py` (derives the compiled decision logic from `determinism.py`/`guards.py`) |
| `fobo/playbook/` | loads and validates the playbook YAML into the knowledge graph | `fobo/web/dependencies.py` (`ensure_seed_data` → `load_playbook`/`loaded_version`), `fobo/reasoning/determinism.py` (`read_playbook`), `fobo/investigation/graph_view.py` (`read_playbook`), `fobo/investigation/steps/reason.py` (`loaded_version`), plus `python -m fobo.playbook.cli validate\|load` |
| `fobo/grounding/` | records every retrieval as a `source_call` row | `steps/gather.py`, `steps/validate.py`, `console_views/calls.py`, the console's Grounding panel and MCP data column |
| `fobo/db/` | SQLAlchemy models and the async session factory | everywhere |
| `fobo/contracts/` | the entity contract shared across the backend (`Caller`, break/adjustment shapes) | `fobo/knowledge_graph/`, `fobo/cause_checks/`, `fobo/investigation/`, `fobo/web/auth.py` (not `console_views`) |
| `seed_data/` | the demo scenario (recs, run history, breaks) loaded on first request | `fobo/web/dependencies.py` (`ensure_seed_data`); also read live by `fobo/web/investigations.py` and `fobo/web/routes/investigations.py` (`breaks_for_rec`, for `/investigate` and `/trace`) and the route modules (`COB`, the default business date), `scripts/`, tests |
| `migrations/` | Alembic migrations for the schema in `fobo/db/` | `alembic upgrade head` |
| `scripts/` | `run_investigation.py` (deterministic run, no LLM), `demo_investigation.py` (one rec end to end), `reset_e2e_db.py` (rebuild `fobo_e2e`) | developers, the e2e harness (`apps/console/e2e/reset-db.mjs`) |
| `tests/` | pytest suite; one file per module or route, named to match what it covers | `pytest -q` |

## apps/console — the Next.js console (`src/`)

Run with `npm run dev` (port 3100); tests with `npx vitest run`; e2e with
`npm run test:e2e` (its own servers on 8101/3101 and database `fobo_e2e`).

| Path | What it is | Main users |
|---|---|---|
| `app/page.js` | the console, served at `/` | every visitor |
| `app/fobo/page.js` | redirects `/fobo` to `/`, for old bookmarks | nobody new; the e2e spec and Playwright config now start at `/` directly, with one cheap assertion that `/fobo` still redirects |
| `app/layout.js` | root layout: fonts, `<html>`/`<body>`, page metadata | Next |
| `app/console.css` | the console's CSS variables and base styles | every component |
| `components/ConsoleApp.jsx` | the console shell: tabs (board / workflow), date picker, top-level state | `app/page.js` |
| `components/board/` | the event board, rec nav, rec detail, status banner, notification bell, analytics | `ConsoleApp.jsx`; `board/constants.js` also imported by `ui/{Pills,BookBar}.jsx`, `adjustments/ConfirmDialog.jsx`, `mcp/Blocks.jsx`, `session/{SessionPanel,ReplyBlocks,AnalysisTurn}.jsx`, `drawers/{BookDrawer,AllAdjustmentsDrawer}.jsx` |
| `components/adjustments/` | the drafted-adjustments panel and its approve/reject confirm dialog | `board/RecDetail.jsx`, `ConsoleApp.jsx` (`ConfirmDialog`), `drawers/{PatternDrawer,AllAdjustmentsDrawer}.jsx` (`RowDecision`) |
| `components/session/` | the Agent One session panel: analysis turn, chat replies | `board/RecDetail.jsx` |
| `components/workflow/` | the Workflow tab: graph view, version list/detail, draft editor, YAML upload/diff | `ConsoleApp.jsx` |
| `components/drawers/` | slide-over drawers: all adjustments, book detail, MCP inspector, break pattern, workflow trace | `ConsoleApp.jsx` only |
| `components/mcp/` | MCP call rendering: tool call cards, data tables, break detail blocks | `drawers/McpInspector.jsx`, `session/`, `adjustments/AdjustmentsPanel.jsx` (`BreakDetailPanel`) |
| `components/ui/` | shared primitives: pills, KPI tiles, drawer shell, pipeline step, icons | everywhere in `components/` |
| `components/data/` | the API clients (`consoleApi.js`, `workflowApi.js`), the recs context, response-to-view adapters | every component that fetches data |
| `components/lib/` | small view helpers: formatting, MCP column defs, session/break-detail shaping | nearly every component folder (`ConsoleApp`, `ui/`, `board/`, `adjustments/`, `mcp/`, `workflow/`, `drawers/`, `session/`, `data/adapt.js`) |
| `lib/apiClient.js` | the `fetch` wrapper (base URL, `Act as` header); callers supply their own `Idempotency-Key` via `extraHeaders` — it doesn't generate one | `components/data/*Api.js`, `workflow/DevCallerSwitch.jsx` (`setDevCaller`) |
| `lib/uuid.js` | a client-side id for idempotency/confirmation keys | `components/workflow/VersionDetail.jsx` |
| `e2e/` | the Playwright spec and its database reset script | `npm run test:e2e` |

## Everything else

| Path | What it is | Main users |
|---|---|---|
| `config/playbook/` | the investigation rules YAML (tests, categories, verdicts, thresholds) that Product Control owns | `fobo/playbook/loader.py`, loaded into the knowledge graph |
| `config/workflow/` | the workflow YAML that seeds version 1 (step order, pauses, settings) | `fobo/investigation/settings.py`, the Workflow tab's Download/Upload |
| `skills/fobo-investigation/SKILL.md` | the skill deployed to the Agent SDK session service | the `session_service` reasoning adapter, which sends only its id (`FOBO_SESSION_SKILL_ID`) — its content is not read by this backend |
| `docs/integration/` | the session-service contract this backend integrates against | the `session_service` reasoning adapter; integration reference |
| `docs/skills/fobo-investigation-cats-vs-motif.md` | the `direct` adapter's system prompt, read from disk at runtime | `fobo/reasoning/prompt.py`; deleting it breaks `FOBO_REASONER=direct` |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | dated design specs and implementation plans; historical once superseded | developers, agents implementing a plan |
| `.superpowers/sdd/` | per-plan task briefs and reports for spec-driven development runs — local only, not in the repo (`.superpowers/sdd/.gitignore` is `*`) | the agents executing each plan's tasks |

## Where to change what

| To change | Edit |
|---|---|
| A playbook rule (which test fires for a cause, evidence required, default verdict, escalation route, policy threshold) | `config/playbook/fobo-cats-vs-motif.yaml`, then `python -m fobo.playbook.cli validate` and `load` |
| The order investigation steps run in, where a run pauses, or a step's settings | the Workflow tab (draft → second-person approval), or `config/workflow/fobo-investigation.yaml` for the seeded version 1 |
| A new investigation step | add it under `fobo/investigation/steps/`, declare its inputs/outputs in `fobo/investigation/step_registry.py`, then it becomes selectable from the workflow config |
| What the console shows for a rec or the board | `fobo/console_views/` (server side) and `apps/console/src/components/board/` or `session/` (client side) |
| A cause check's logic or its controller-facing wording | `fobo/cause_checks/checks.py` or `fobo/cause_checks/reasons.py` |
| How judgement-based breaks are reasoned about | `fobo/reasoning/` (the port, guards, adapters); the `direct` adapter's prompt is `docs/skills/fobo-investigation-cats-vs-motif.md` (read by `reasoning/prompt.py`), the `session_service` adapter instead names the deployed `skills/fobo-investigation/SKILL.md` by id |
