# Codebase Naming Cleanup — Design

**Date:** 2026-09-26 · **Status:** approved in conversation · **Branch:** `refactor/naming-cleanup`

## 1. Purpose

A developer opening this repo should know what each folder is for from its
name. Today they can't: the backend has two sibling packages called `api/` and
`app/`; "graph" means both the knowledge graph and the LangGraph workflow;
`helix`, `recon`, `cases` and `fixtures` are codenames or misleading words; and
the console carries a retired UI (`components/fobo`, served at `/classic`)
beside the current one (`components/helix`, served at `/` **and** `/fobo`).

The user asked to **keep only the code that is needed** and to **rename every
module with a name that says what it does**, including the API paths.

## 2. Rules

- **No behaviour change** beyond the removals and the API path renames listed
  here. The investigation, the workflow configuration, the four-eyes rules, the
  console's screens and the seed data behave exactly as before.
- **Tests move with their code.** A test changes only its import paths, URL
  paths, or is deleted because the code it covers is deleted.
- Function and class names stay, except where listed (§5).
- Historical documents (`docs/superpowers/specs|plans` dated before this one)
  are not rewritten — they record the state at the time.
- Every step ends green: backend suite, console suite, and the Playwright e2e.

## 3. Removed (git history keeps it)

"Needed" = reachable from the current console, the Workflow tab, the
investigation engine, the CLIs, the README scripts, the e2e test, and
migrations. Computed with an import-reachability scan and a route/URL scan.

**Console:** `src/app/(classic)/`, `src/components/fobo/`,
`src/store/fobo*Store.js` (7), `src/hooks/useRunStream.js`,
`src/lib/WebSocketClient.js`, and their tests; the `zustand` dependency if
nothing else uses it.

**Backend routes used only by the classic console:** `api/routes/runs.py`
(`/api/runs`), `api/routes/worklist.py` (`/api/activity`, `/api/worklist`),
`api/routes/analytics.py`, `api/routes/books.py`, `api/routes/breaks.py`,
`api/websocket/` (`/api/ws/runs`).

**Backend code only those use:** `app/queries/activity.py`,
`app/queries/schedule.py`; `fixtures/ontology.py` (imported by nothing); the
websocket event models in `app/contracts/models.py` (`WS_EVENT_MODELS` and the
event classes only they use); `packages/contracts/` (it only generates types
for those events).

**Replaced by the API consolidation (§5):** the old rec-detail route
`GET /api/recs/{id}`, `api/routes/sessions.py`, and the classic decision route
`POST /api/recs/{id}/decisions` — their still-needed logic moves (§4, §5).

## 4. New layout

```
apps/backend/                         (was apps/api — the FastAPI service)
  fobo/                               one package (was two: api/ + app/)
    web/                              HTTP layer                      (was api/)
      main.py, auth.py
      dependencies.py                                                 (was deps.py)
      investigations.py               open / run / read an investigation (was cases.py)
      routes/
        console.py                    board, rec detail, chat, decisions (was routes/helix.py + decisions logic)
        investigations.py             run one, trace                  (was routes/recs.py + sessions.py)
        workflow_config.py            versions, drafts, graph         (was routes/workflow.py)
    investigation/                    the LangGraph investigation    (was app/workflow/)
      graph.py, state.py, session.py, versions.py, graph_view.py, diff.py, yaml_io.py, cli.py
      steps/                          one module per graph step       (was nodes/)
      step_registry.py                                               (was registry.py)
      settings.py                                                    (was config.py)
    knowledge_graph/                  books, desks, lineage (bitemporal) (was app/graph/)
      queries/ (was graph/queries/), repository.py, ontology.py, entitlement.py, errors.py
    cause_checks/                     C1–C6 cause checks              (was app/recon/)
    console_views/                    what the console shows          (was app/helix/)
    reports/                          analytics, execution trace      (was app/queries/)
    reasoning/, playbook/, grounding/, db/, contracts/   (unchanged names)
  seed_data/                          demo scenario loaded on first request (was fixtures/)
  migrations/, scripts/, tests/, alembic.ini, pyproject.toml
apps/console/src/
  app/page.js                         the console, at "/"
  app/fobo/page.js                    redirects to "/"  (old bookmarks)
  components/                         (was components/helix/, flattened)
    ConsoleApp.jsx (was HelixApp.jsx), board/, adjustments/, session/, workflow/, drawers/, mcp/, ui/, data/, lib/
  lib/ (apiClient, uuid), styles/
docs/ARCHITECTURE.md                  one entry per folder: what it is, who uses it
```

The Python distribution becomes `fobo-backend`; `pyproject.toml` packages
`fobo*` (the package tree) plus `seed_data`. Commands become
`python -m fobo.investigation.cli …`, `python -m fobo.playbook.cli …`,
`uvicorn fobo.web.main:app`.

## 5. API paths and the few renamed functions

| Old | New |
|---|---|
| `GET /api/helix/board` | `GET /api/board` |
| `GET /api/helix/recs/{id}` | `GET /api/recs/{id}` (the console's rec view) — *amended during review:* removed instead; nothing in the console called it (`fetchRec` was only mocked in a test), and `GET /api/board` already returns the same per-rec view |
| `POST /api/helix/recs/{id}/messages` | `POST /api/recs/{id}/messages` |
| `POST /api/helix/recs/{id}/decisions` | `POST /api/recs/{id}/decisions` (the console's decision; the classic body shape is dropped) |
| `GET /api/recs/{id}` (classic detail; also used to *start* a run) | `POST /api/recs/{id}/investigate` — runs the investigation if it has not run, returns `{session_id, status, workflow_version}` |
| `GET /api/recs/{id}/trace` | unchanged |
| `POST /api/sessions/{id}/investigate`, `GET /api/sessions/{id}` | removed (use `POST /api/recs/{id}/investigate`) |
| `/api/workflow/*` | unchanged |

Renamed functions: `open_case` → `open_investigation`, `read_case` →
`read_investigation`, `ensure_fixtures` → `ensure_seed_data`,
`session_id_for` stays. The `helixApi.js` client becomes `consoleApi.js`.

## 6. Verification

After each step: `pytest -q` (backend), `npx vitest run` (console, 3 runs),
`npm run test:e2e`. After the backend move, a fresh virtualenv is created in
`apps/backend/.venv` (virtualenvs cannot be moved). The user's dev servers are
restarted from the new paths at the end, with the same flags they used.
