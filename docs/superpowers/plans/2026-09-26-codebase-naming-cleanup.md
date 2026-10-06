# Codebase Naming Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Remove the retired classic console and everything only it uses, and rename every module so its name says what it does (spec §4–5).

**Architecture:** Five steps, each ending green. Removal first (less to move), then the API consolidation in the old layout, then the backend package move, then the console restructure, then docs.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, Alembic, pytest (apps/api → apps/backend); Next 16, React 19, vitest, Playwright (apps/console).

**Spec:** `docs/superpowers/specs/2026-09-26-codebase-naming-cleanup-design.md` (read §2 Rules first).

## Global Constraints

- No behaviour change beyond the spec's removals and API renames. Tests change only paths/imports, or are deleted with the code they cover.
- Use `git mv` for every move so history follows the files.
- Every task ends with: backend `pytest -q` green; console `npx vitest run` green 3 runs, pristine; `cd apps/console && npm run test:e2e` green (it runs its own servers on 8101/3101 and database fobo_e2e).
- The user's dev servers (console 3100 from apps/console, API 8100 from apps/api with --reload) run from this checkout. Do not stop them; if a task's changes break the running API (expected in Task 3), say so in the report — the controller restarts them at the end.
- Commits: `<type>: <description>`, ending with your environment's Co-Authored-By line (if none: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Never push.
- Historical docs dated before 2026-09-26 under docs/superpowers are not edited.

## Review Focus

1. A removed route or module still imported or called somewhere (tests, scripts, e2e, README commands) — grep for every old name after each task.
2. The e2e test and `scripts/run_investigation.py` still start runs after `GET /api/recs/{id}` stops being a trigger.
3. Alembic still finds the models and migrations after the move (`alembic upgrade head` on the dev DB is a no-op, not an error).
4. `defined_in` paths shown in the Workflow tab ("How it decides") point at the new file paths.
5. Next's route change: `/` serves the console, `/fobo` redirects, `/classic` is gone (404), and no dead imports remain.

---

### Task 1: Retire the classic console

**Remove (git rm):** `apps/console/src/app/(classic)/`, `apps/console/src/components/fobo/`, `apps/console/src/store/` (all `fobo*Store.js` and tests), `apps/console/src/hooks/useRunStream.js`, `apps/console/src/lib/WebSocketClient.js` (+ tests); `apps/api/api/routes/{runs,worklist,analytics,books,breaks}.py`, `apps/api/api/websocket/`; `apps/api/app/queries/{activity,schedule}.py`; `apps/api/fixtures/ontology.py`; `packages/contracts/`.

- [ ] Before deleting, grep each removed module/route/path for other users (backend `api/`, `app/`, `fixtures/`, `scripts/`, `tests/`; console `src/`, `e2e/`); anything outside the removal set that uses them must be reported, not silently broken. Known: none per the reachability scan.
- [ ] `apps/api/api/main.py`: drop the removed routers and the websocket include.
- [ ] `apps/api/app/contracts/models.py`: remove `WS_EVENT_MODELS` and the event models only it references (keep everything else, e.g. `Caller`, `BreakRecord`); `apps/api/tests/test_contracts.py`: drop assertions on removed models only.
- [ ] Delete tests that only cover removed code (e.g. tests for runs/worklist/analytics/books/breaks/schedule/activity routes or queries, the websocket, the classic stores/components). Keep tests of retained code, rewriting only their imports if needed.
- [ ] Console: remove `zustand` from `package.json` if nothing imports it (`npm uninstall zustand`); remove other deps only if certain they're unused.
- [ ] README: drop the classic console section/lines and any command for removed pieces; keep everything else.
- [ ] Verify (backend, console ×3, e2e). Commit `refactor: retire the classic console and what only it used`.

### Task 2: Consolidate the API paths (old layout)

In `apps/api` (paths per spec §5):
- [ ] New `api/routes/investigations.py` (router prefix `/api/recs`): `POST /{rec_id}/investigate` — `ensure_fixtures`, `rec_and_run`, `open_case`; if the rec has no breaks → 409 "nothing to investigate"; returns `{"session_id", "status" ("awaiting_signoff" | "escalated" | "recorded" | …, read from the checkpoint as the trace does), "workflow_version"}`; and move `GET /{rec_id}/trace` here from `recs.py` unchanged.
- [ ] `api/routes/aof.py`: change the prefix from `/api/aof` to `/api` so its paths become `/api/board`, `/api/recs/{id}`, `/api/recs/{id}/messages`, `/api/recs/{id}/decisions`. Move the still-needed decision logic (`DecisionRequest`, `apply_decision`, `_already_recorded` …) out of `api/routes/decisions.py` into `api/decisions.py` (a non-route module) and import it from there.
- [ ] Delete `api/routes/recs.py` (its trace route moved), `api/routes/sessions.py`, `api/routes/decisions.py` (route file); anything else they exported that is still used (e.g. `PIPELINE_STAGES`) moves next to its user. Register the routers in `main.py` so no two routes collide (`/api/recs/{id}` GET is now the console view).
- [ ] Update every caller: console `src/components/aof/data/aofApi.js` (board/recs/messages/decisions/trace URLs), `e2e/workflow.spec.js` (use `request.post(\`${API}/api/recs/R-2031/investigate\`)` to start the run), `scripts/run_investigation.py` (POST investigate), backend tests (rewrite URLs; tests of removed classic-only response shapes are deleted; tests that used `GET /api/recs/{id}` or `/api/sessions/...` to *start* a run switch to `POST /api/recs/{id}/investigate`), README.
- [ ] Add tests: `POST /api/recs/R-1055/investigate` → 200 with `workflow_version` and a status; a second POST does not re-run (same session, same checkpoint count); unknown rec → 404; rec without breaks → 409; `GET /api/aof/board` → 404 (old path gone).
- [ ] Verify (backend, console ×3, e2e). Commit `refactor: one set of API paths for the console and investigations`.

### Task 3: Move the backend to `apps/backend/fobo`

- [ ] `git mv apps/api apps/backend`. Inside: `git mv api fobo_web_tmp` … arrange exactly the spec §4 tree: `fobo/__init__.py`; `api/` → `fobo/web/` (`deps.py` → `dependencies.py`, `cases.py` → `investigations.py`, `routes/aof.py` → `routes/console.py`, `routes/workflow.py` → `routes/workflow_config.py`, `routes/investigations.py` stays); `app/workflow/` → `fobo/investigation/` (`nodes/` → `steps/`, `registry.py` → `step_registry.py`, `config.py` → `settings.py`); `app/graph/` → `fobo/knowledge_graph/`; `app/recon/` → `fobo/cause_checks/`; `app/aof/` → `fobo/console_views/`; `app/queries/` → `fobo/reports/`; `app/{reasoning,playbook,grounding,db,contracts}` → `fobo/…`; `fixtures/` → `seed_data/`.
- [ ] Rewrite every import to the new dotted paths across `fobo/`, `seed_data/`, `scripts/`, `tests/`, `migrations/env.py` (a scripted rewrite is fine; then grep that no `from app.`/`import app`/`from api.`/`from fixtures.`/`api.`-prefixed module strings remain, including `monkeypatch.setattr("...")` targets and `mock.patch` strings).
- [ ] Renames inside code (spec §5): `open_case` → `open_investigation`, `read_case` → `read_investigation`, `ensure_fixtures` → `ensure_seed_data` (all call sites).
- [ ] Path constants that count parents (`REPO_ROOT = Path(__file__).resolve().parents[N]` in settings.py, playbook loader, graph_view `defined_in`, anything else using `parents[`) — fix N for the new depth; the Workflow tab's `defined_in` must show `apps/backend/fobo/...`; update tests asserting those paths.
- [ ] `pyproject.toml`: name `fobo-backend`; `[tool.setuptools] packages` → find `fobo*` and `seed_data` (e.g. `[tool.setuptools.packages.find] include = ["fobo*", "seed_data*"]`); `pythonpath = ["."]` stays. `alembic.ini` unchanged unless paths break.
- [ ] Fresh venv: `cd apps/backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"` (the old `apps/api/.venv` is left for the controller to remove after restarting servers; do not delete it — the user's running API uses it). Delete any stale `*.egg-info` in the moved tree.
- [ ] Update commands everywhere: `python -m fobo.investigation.cli`, `python -m fobo.playbook.cli`, `uvicorn fobo.web.main:app`; CLI docstrings; `apps/console/playwright.config.js` (webServer cwd `../backend`, `uvicorn fobo.web.main:app`), `e2e/reset-db.mjs` (path `../../backend`), `scripts/reset_e2e_db.py` imports; `.claude/hooks/session-start.sh`, `.cursor/*.sh` and `.cursor/environment.json` (paths `apps/backend`, commands); README; `config/playbook/*.yaml` and `config/workflow/*.yaml` header comments (command paths only); `docs/integration/session-service-contract.md` (paths only). Regenerate `apps/console/src/components/aof/workflow/__fixtures__/graph.json` with the new `defined_in` paths using the same generator snippet as before (imports updated).
- [ ] Verify: backend suite from `apps/backend`; `alembic upgrade head` against the dev DB is a no-op; console ×3; e2e. Commit `refactor: one backend package, fobo/, named by what each part does`.

### Task 4: Flatten and rename the console

- [ ] `src/app/(aof)/` → `src/app/` (layout.js, page.js, aof.css → `src/app/console.css`; update imports); `/fobo` becomes `src/app/fobo/page.js` that redirects to `/` (read `node_modules/next/dist/docs/` for `redirect()` in this Next 16 first); `/classic` route no longer exists.
- [ ] `src/components/aof/*` → `src/components/*` with folders: `board/` (EventBoard, RecNav, RecDetail, BoardStatus, NotificationBell, Analytics, constants), `adjustments/`, `session/`, `workflow/`, `drawers/`, `mcp/`, `ui/`, `data/` (`aofApi.js` → `consoleApi.js`, workflowApi.js, adapt, RecsContext), `lib/` (merge with `src/lib` only if no name collision; otherwise keep `components/lib` as is); `AofApp.jsx` → `ConsoleApp.jsx` (component renamed `ConsoleApp`); `__fixtures__/` stay next to their tests. Update every import and `vi.mock(...)` path.
- [ ] `src/app/console.css` keeps the same CSS variables; no visual change.
- [ ] Verify: console ×3 pristine; `NEXT_DIST_DIR=.next-build npx next build` succeeds (then delete `.next-build/`); e2e. Take a 1440×900 screenshot of `/` via Playwright against the e2e servers or note that the user's 3100 dev server shows the console unchanged. Commit `refactor: the console lives at src/components, named by feature`.

### Task 5: Architecture map and docs

- [ ] New `docs/ARCHITECTURE.md`: a tree of the repo's folders (apps/backend/fobo/*, seed_data, migrations, scripts, tests; apps/console/src/*; config/; skills/; docs/) with one line each — what it is, who uses it — plus a "request flow" paragraph (console → /api/board → console_views → investigation graph → knowledge_graph / cause_checks / reasoning → db) and a "where to change what" table (playbook rules → config/playbook; workflow order/settings → Workflow tab / config/workflow seed; a new step → fobo/investigation/steps + step_registry).
- [ ] README: update all paths/commands; link ARCHITECTURE.md near the top; remove anything describing removed code.
- [ ] Final grep for old names across non-historical files: `apps/api`, `from app.`, `api.routes`, `components/aof`, `AofApp`, `aofApi`, `/api/aof`, `fixtures.` (Python), `open_case`, `read_case`, `ensure_fixtures`, `/classic` — every hit is either fixed or in a historical doc.
- [ ] Verify all suites + e2e once more. Commit `docs: architecture map and README for the new layout`.
