# Agent One Finance in the office: conversion guide

**For:** you and office Claude Code, bringing Agent One Finance (AOF) from this repository into the
office repos `aos-frontend` and `aos-backend`, and running the AOF service on AWS.

**This is the only guide.** It replaces every earlier migration, update and conversion page (now in
[`../archive/`](../archive/README.md), for the record only). It is written for the office layout
reported in `aos-structure.md` (9 Oct 2026):

- `aos-frontend`: Next.js 16.1.1 with webpack, React 19, JSX, Tailwind 4, `basePath /agentone`,
  next-themes and BAM single sign-on;
- `aos-backend`: Python 3.12, `app/requirements.txt`, the AOF image built from `Dockerfile.helix`
  on port 8300, ECS task definitions.

## 1. The rule: the conversion happens here, not in the office

Every earlier update was converted by hand in the office: 58 files from TSX to JSX, Vite routes to
Next.js routes, Tailwind 3 to 4. That lost the styles and the menu icons, missed the newest screens,
and took 8 fix-up commits.

Now the conversion is one script in this repository, run the same way every time:

- `apps/web/office/convert.mjs` turns the console into `aos-frontend`'s shape and commits the result
  in [`office/aos-frontend/`](../../../office/aos-frontend). A test fails if that folder is out of date.
- `office/aof_sync.py` copies it, and the AOF backend, into the office repos. It keeps the office's
  own changes with a three-way merge.

**Office Claude never converts or restyles code.** It runs the sync, settles anything the sync marks,
builds, tests and reports.

## 2. What goes where

| Upstream (this repository) | Office | Notes |
|---|---|---|
| `office/aos-frontend/src/app/finance/**` (made from `apps/web`) | `aos-frontend/src/app/finance/**` | The Next.js pages for `/finance`, and the console's code in the private folder `_aof/` (Next.js ignores `_` folders for routing). **The sync reads and writes nothing else in aos-frontend.** |
| `apps/backend/agent_one_finance` | `aos-backend/agent_one_finance` | `session_bridge.py` stays the office's |
| `apps/backend/migrations` | `aos-backend/aof_migrations` | See section 6 step 2 before the first sync |
| `config/agent-one-finance` | `aos-backend/config/agent-one-finance` | `connectors.yaml` stays the office's |
| `apps/backend/seed_data/aof_documents` | `aos-backend/seed_data/aof_documents` | Sample documents for the documents service |
| `apps/backend/tests/agent_one_finance` | `aos-backend/tests/agent_one_finance` | |
| `apps/backend/pyproject.toml` dependencies | `aos-backend/app/requirements.txt` | The sync report lists anything missing; add it by hand |

Not AOF, and never touched by the sync:

- `src/components/financeagent/` and `/financeagent`: Agent One's own Finance Agent;
- `/fobo`, `Dockerfile.fobo`: the original FOBO app, retired after go-live;
- `api/routes/aof_*.py`: the main API's own routes into AOF.

## 3. How the converted console fits aos-frontend

This was checked in a Next.js app set up like aos-frontend:

- Next.js 16.1.1, built with `next build --webpack`;
- `basePath: "/agentone"`;
- React 19.2.3, Tailwind 4 with a `tailwind.config.js` (`darkMode: ["class"]`);
- next-themes, lucide-react 0.562, eslint-config-next.

The results:

- the build passes and lint is clean;
- every page loads with no browser errors;
- links and the left menu go to `/agentone/finance/...`;
- the icons show;
- the console's theme button switches Agent One's theme too;
- Agent One's own pages look exactly as before.

| Part | In aos-frontend |
|---|---|
| Routes | `/finance` (Overview), `/finance/inbox`, `/finance/capabilities`, `/finance/capabilities/[id]`, `/finance/capabilities/[id]/groups/[group]`, `/finance/cases/[caseId]`, `/finance/authoring`, `/finance/operations`, `/finance/audit`, `/finance/connectors`. Each is a small `page.jsx` that loads the console page in the browser. |
| Frame | `src/app/finance/layout.jsx` wraps the finance pages in `_aof/office/FinanceShell.jsx`: the console's query cache, its left menu and top bar. |
| Navigation | `_aof/office/router.js` gives the console's links Next.js navigation. `basePath` is added by Next.js. |
| Styles | `_aof/finance.css` is compiled here and scoped to `#aof-root`. It needs no change to Agent One's Tailwind set-up and does not change Agent One's pages. |
| Theme | Follows Agent One's light and dark theme (next-themes), so there is one theme switch for the whole page. |
| Height | The console fills the viewport by default. Under Agent One's header, set `--aof-height`, for example `calc(100vh - 64px)`, on an element around it. |
| Packages | `@tanstack/react-query`, `clsx`, `yaml`, `lucide-react` and `next-themes`. aos-frontend already has them all. |
| Sign-on | `_aof/office/auth.js` is **the one console file the office owns**. It returns the headers Agent One's API needs on each AOF call, for example the BAM token from `src/lib/sso.js`. The sync adds it once and never overwrites it. |
| API address | `NEXT_PUBLIC_AOF_API=/agentone/api/finance`, set in `.env.development`, `.env.uat` and `.env.production`. The console calls `/agentone/api/finance/...`, and Next.js rewrites `/api/finance/*` to the AOF service (section 8). |
| Lint | Add `{ ignores: ["src/app/finance/_aof/**"] }` to `eslint.config.mjs`. That code is linted and type-checked upstream, in TypeScript. |

## 4. The workspace

```
Skillgap/
  fobotower-main/       the latest download of this repository (main), replaced on every update
  aos-frontend/         office repo
  aos-backend/          office repo
  aof-sync.json         optional: only if the office folder names differ from section 2
  aof-sync-base/        kept by the sync tool: what upstream looked like at the last sync. Do not delete.
  aof-sync-report.md    written by every run
```

Each office repo also gets `.aof-sync.json`, recording what was synced and when. Commit it.

## 5. What the sync does with each file

| In the report | Meaning | What to do |
|---|---|---|
| `add`, `update`, `remove` | Upstream changed a file the office never edited | Nothing |
| `keep-office` | Only the office changed it, or it is an office file (`auth.js`, `connectors.yaml`, `session_bridge.py`) | Nothing |
| `merge` | Both changed it, in different places; merged | Look at the diff |
| `clash` | Both changed the same lines, marked `<<<<<<< office` … `>>>>>>> upstream` | Settle by hand. The next run refuses to apply until no marks are left. |
| `differs` | First sync only: the office file differs and there is no base to merge from | Review; `--baseline` takes upstream |
| `office-only` | A file upstream does not have. In `src/app/finance` it is a leftover of the hand conversion; elsewhere it is the office's own | `--baseline --prune` removes leftovers in `src/app/finance` only |
| Packages to add | Upstream needs a Python package that `app/requirements.txt` does not list | Add it |

## 6. First time: replace the hand conversion (once)

1. **Get the code.**
   - Download `main` of this repository as a zip and unpack it as `Skillgap/fobotower-main`.
   - Download `https://github.com/praveen2025work/fobotower/archive/dbaac6f.zip` and unpack it as
     `Skillgap/fobotower-base`. That is the backend version the office last copied. It lets the
     sync merge office edits instead of overwriting them.
2. **Settle the migrations** (the AOF database on AWS).
   - The office has `helix_migrations` (18 versions, an older lineage) and removed `aof_migrations`.
     The AOF code needs the upstream lineage: 25 versions, head `e7f9a1b3c5d7`.
   - Ask office Claude to read the UAT AOF database's `alembic_version` table, and the list of its
     tables, and send me the result. There are three cases:
     - **An upstream id** (any file name in `apps/backend/migrations/versions`): restore
       `aof_migrations` through the sync, with an `aof_alembic.ini` (`script_location = aof_migrations`),
       then run `alembic -c aof_alembic.ini upgrade head`.
     - **No `alembic_version` table** (created by deployment scripts): restore `aof_migrations`. Run
       `alembic -c aof_alembic.ini stamp e7f9a1b3c5d7` once, only if `alembic -c aof_alembic.ini check`
       reports no differences.
     - **A `helix_migrations` id**: stop and send me the tables. The database needs a one-off step
       to join the upstream lineage.
3. **Paste the first-time prompt below** into office Claude.

> We are bringing Agent One Finance into aos-frontend and aos-backend with the upstream sync tool.
> Read `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md` first and follow it.
> Do not convert, restyle or rewrite any upstream file yourself; if something does not work, tell me
> what and why.
>
> Work on a new branch `aof-sync` in both repos. Do not touch the main branch, any deployment,
> database or secret. Stop after each step and show me the result.
>
> 1. **Dry run.** From `Skillgap`, run
>    `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main --base-from fobotower-base`
>    and show me `aof-sync-report.md`. Then:
>    - **Frontend:** every file under `src/app/finance` from the hand conversion will be replaced.
>      List any file outside `src/app/finance` that imports from `src/app/finance` (for example
>      `src/components/finance/FinanceCasesWidget.jsx`). Each must be re-pointed to
>      `src/app/finance/_aof/...` in step 3.
>    - **Frontend leftovers outside `src/app/finance`:** list the files the hand conversion added
>      elsewhere: the `ui.tsx` split in `src/components/ui/`, and `useIsPhone.js` and
>      `useStickyBottom.js` in `src/components/financeagent/layout/`. For each, say whether anything
>      other than the old `src/app/finance` files imports it. Do not touch Agent One's own files,
>      including the Finance Agent in `src/components/financeagent/`.
>    - **Backend:** for each `differs`, `clash` or `office-only` file, show me the diff and say
>      whether it is an office change to keep.
> 2. **Apply.** Once I agree, run the same command with `--apply --baseline --prune`, then show the
>    report and `git status` for both repos.
> 3. **Office wiring (aos-frontend).** Do each step the way the rest of aos-frontend is written.
>    - Port our BAM sign-on into `src/app/finance/_aof/office/auth.js`. It returns the headers our
>      API needs. The old hand-converted `api/client.js` and the SSO bridge commit (d9db52a) show
>      what we sent.
>    - Set `NEXT_PUBLIC_AOF_API=/agentone/api/finance` in `.env.development`, `.env.uat` and
>      `.env.production`.
>    - Add `{ ignores: ["src/app/finance/_aof/**"] }` to `eslint.config.mjs`.
>    - Re-point the importers from step 1 to `src/app/finance/_aof/...`.
>    - Remove the leftovers I approved in step 1, and `docs/helix-ui-reference/`.
>    - Check the Finance entry in `src/components/sidebar/Sidebar.jsx` goes to `/finance`.
>    - If the page has a fixed header, set `--aof-height` (guide section 3).
> 4. **Backend wiring (aos-backend).**
>    - Add the packages the report lists to `app/requirements.txt`.
>    - Make sure `Dockerfile.helix` copies `aof_migrations`, `config/agent-one-finance` and
>      `seed_data/aof_documents`.
>    - Add those folders to the `.gitlab-ci-aof.yml` trigger paths.
> 5. **Check.**
>    - aos-frontend: `npm run lint` and `npm run build:uat`.
>    - aos-backend: `pytest -q tests/agent_one_finance` and `alembic -c aof_alembic.ini heads` (one
>      head, `e7f9a1b3c5d7`).
>    - Then run both against UAT. Give me screenshots of `/agentone/finance`, a case and a
>      capability's "How it runs" tab, light and dark. Confirm the left-menu icons show.
> 6. **Commit** in each repo, including `.aof-sync.json`, and summarise:
>    - what was replaced, merged, kept and removed;
>    - the wiring done;
>    - the check results.
>
>    Stop there; I will raise the merge requests.

## 7. Every update after that

1. Replace `Skillgap/fobotower-main` with a new download of `main`.
2. Paste:

> Update Agent One Finance from upstream with the sync tool, as
> `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md` section 7 says. Use a new
> branch `aof-sync-<date>` in both repos. Never convert or rewrite upstream files yourself.
>
> 1. Run `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main` from `Skillgap` and show
>    me the report.
> 2. Once I agree, run it with `--apply`.
>    - For each `clash`, show me the marked lines, propose how to settle them, and wait for my OK.
>    - Then run it again until it applies cleanly.
> 3. Add any packages the report lists. If `apps/backend/migrations` changed, run
>    `alembic -c aof_alembic.ini upgrade head` on UAT only after I agree.
> 4. Run the checks from section 6 step 5.
> 5. Commit in each repo with `.aof-sync.json`, and summarise as in section 6 step 6.

## 8. The AOF service on AWS

`aos-backend` already builds the AOF image (`financeagent-aof-backend` from `Dockerfile.helix`, port
8300, pipeline `.gitlab-ci-aof.yml`), and the AOF database (Postgres with pgvector) exists. What is
left is AOF's own ECS service.

| | |
|---|---|
| Task definition | `ecs-task-definition-aof.json`, made like `ecs-task-definition-fobo.json`. Family `agentone-aof-family`, container `aof-backend`, port 8300, image `financeagent-aof-backend`. |
| Start | `uvicorn agent_one_finance.web.main:app --host 0.0.0.0 --port 8300 --workers 3` |
| Health check | `curl -f http://localhost:8300/health` |
| Image | Python 3.12 from Nexus. `app/requirements.txt` must keep `sqlalchemy[asyncio]` and `greenlet>=3.0`; it already does. |
| Database | Either `AOF_DATABASE_URL`, or its parts `AOF_DATABASE_HOST`, `AOF_DATABASE_PORT`, `AOF_DATABASE_NAME`, `AOF_DATABASE_USER` and `AOF_DATABASE_PASSWORD`. Each part can be one key of the database secret in Secrets Manager (`valueFrom: <secret arn>:<key>::`). AOF builds the URL itself. |
| Migrations | Before each deployment, a one-off task with the same image: `alembic -c aof_alembic.ini upgrade head` (see section 6 step 2). |
| Required settings | `AOF_CONFIG_DIR=/app/config/agent-one-finance` and `AOF_DOCUMENTS_DIR=/app/seed_data/aof_documents`, or wherever the Dockerfile puts them. The defaults assume the upstream folder layout, so the office must set both. |
| Other settings | `AOF_LLM_ADAPTER` (the office adapter), `AOF_IDENTITY_HEADER`, `AOF_TRUSTED_PROXY_SECRET`, `AOF_PROXY_SECRET_HEADER`, `AOF_CONSOLE_ORIGIN` and `AOF_CONSOLE_URL` (Agent One's address, with `/agentone/finance`), `AOF_ENTITLEMENT_URL`, `AOF_ENV_NAME` (`uat`, `prod`), `AOF_RUN_MODE`, `AOF_SCHEDULER`, `AOF_REPORTS_STORE`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME`. Each is described at the top of `agent_one_finance/config.py`. |
| From the frontend | Today `next.config.mjs` rewrites `/api/finance/*` to `{API_URL}/finance/api/*`, the main API on 8000. Once AOF has its own service, point that rewrite at it: `{AOF_API_URL}/api/*`. Before changing it, ask office Claude to show how 8000 serves `/finance/api` today (`api/routes/aof_*.py` or a proxy). |

Checks after each deployment:

```bash
curl -s https://<aof-service>/health
curl -s -H "<identity header>: <a test user>" https://<aof-service>/api/me
```

After go-live, retire FOBO: `Dockerfile.fobo`, `ecs-task-definition-fobo.json`, the FOBO pipeline
trigger, and `/fobo` in aos-frontend.

## 9. Changing the conversion (upstream only)

In this repository:

1. After any console change, run `cd apps/web && npm run office:build`.
2. Commit `office/aos-frontend` with the change. `npm test` fails if you forget.

To change how the console is converted, edit `apps/web/office/convert.mjs` and
`apps/web/office/templates/`:

- `router.js` and `FinanceShell.jsx`;
- `theme.js`, the office version of `src/theme.ts`;
- `auth.js`, the office-owned starting point.

Then check the result in a Next.js app set up like aos-frontend (section 3).
