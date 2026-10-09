# AOF conversion pack

**This folder is the whole pack.** It takes Agent One Finance (AOF) into `aos-frontend` and `aos-backend`, and runs
the AOF API on AWS next to the Agent One API. It is written for the structure of both repos as they stand
(`aos-structure.md`, 9 Oct 2026). Earlier guides are in `docs/agent-one-finance/archive/`; do not use them.

## For the person

1. Download `main` of `praveen2025work/fobotower` (Code → Download ZIP). Unzip it as `Skillgap/fobotower-main`,
   replacing any older copy. That is the only download; the pack carries the earlier AOF releases it needs.
2. Paste **prompt A** (section 8) into office Claude the first time, and **prompt B** for every later release.
3. Office Claude stops after each step. Read what it shows and say OK.

## What is in the pack

| In `fobotower-main/office/` | What it is |
|---|---|
| `aos-frontend/src/app/finance/` | The AOF console, already in aos-frontend's shape: Next.js App Router pages for `/finance`, JSX, and styles that do not depend on Agent One's Tailwind. Made by `apps/web/office/convert.mjs`, and tested in a Next.js 16.1.1 / webpack / `basePath /agentone` / Tailwind 4 / next-themes app. |
| `aof_sync.py` | Copies AOF into both repos and keeps the office's own changes (three-way merge). Needs Python 3.9+ and git only. |
| `aof-history.json`, `aof-history.tar.gz` | Every earlier AOF release of the synced files. The first sync uses them to tell untouched old files (updated) from files the office edited (merged). |
| `hosting/Dockerfile.aof` | The AOF API image (port 8300) |
| `hosting/aof_alembic.ini` | Migration settings for `aof_migrations/` |
| `hosting/aof_forward.py` | Reference for the Agent One API route that forwards `/finance/api/*` to the AOF service |
| `hosting/deploy-options.md` | The two ways to run the AOF container on ECS, step by step: A (its own service, recommended) and B (a container in `agentoneapi-family`) |

## 1. Rules for office Claude

1. **Never convert, restyle or rewrite AOF code by hand.** Everything under `src/app/finance` (frontend) and the
   synced backend folders comes from the pack, unchanged.
2. **Copy with `aof_sync.py` only.** Run it without `--apply` first and show the report.
3. **Work on a branch in each repo.** Never touch the main branch, a deployment, a database or a secret without an
   OK.
4. **Stop after each numbered step** and show the result.
5. If something fails, say what and why. Do not work around it by editing AOF code.

## 2. Where everything goes

### aos-frontend

| Path | What happens |
|---|---|
| `src/app/finance/**` | **Replaced by the pack.** The 28 hand-converted files go: `api/aof.js`, `api/client.js`, `components/*`, `FinanceConsole.jsx`, `FinanceLayout.jsx`, and the old `page.js` and `layout.js`. In their place come the pack's pages and its code in the private folder `src/app/finance/_aof/`. |
| `src/app/finance/_aof/office/auth.js` | **Ours.** Returns the headers every AOF call needs: the same BAM token our other API calls send (`src/lib/sso.js`). The sync adds it once and never overwrites it. |
| `.env.development`, `.env.uat`, `.env.production` | Add `NEXT_PUBLIC_AOF_API=/agentone/api/finance` |
| `next.config.mjs` | No change. The rewrite `/api/finance/*` → `{API_URL}/finance/api/*` stays. |
| `eslint.config.mjs` | Add `{ ignores: ["src/app/finance/_aof/**"] }`. That code is linted and type-checked in TypeScript before it reaches the pack. |
| `src/app/globals.css` | Add `#aof-root { --aof-height: calc(100vh - <Agent One header height>); }` so the console fits under the header |
| `src/components/sidebar/Sidebar.jsx` | The Finance entry links to `/finance` |
| `src/components/finance/FinanceCasesWidget.jsx` | Re-point its imports from the old `src/app/finance/api/aof.js` to `@/app/finance/_aof/api/aof` |
| Left over from the hand conversion, outside `src/app/finance` | The `ui.tsx` split in `src/components/ui/`, `useIsPhone.js` and `useStickyBottom.js` in `src/components/financeagent/layout/`, and `docs/helix-ui-reference/`. Remove each one that nothing else imports. |
| `src/components/financeagent/**`, `/financeagent` | **Not AOF.** This is Agent One's Finance Agent; never touched. |
| `/fobo` | The original FOBO screens; removed after go-live |

Packages: `@tanstack/react-query`, `clsx`, `yaml`, `lucide-react` and `next-themes` are needed, and aos-frontend
already has them all.

### aos-backend

| Path | What happens |
|---|---|
| `agent_one_finance/**` | **Synced from the pack.** `session_bridge.py` stays ours. |
| `aof_migrations/**` | **Synced from the pack.** It comes back after commit 7fe06a9 removed it: the AOF code needs AOF's own migration history (25 versions, head `e7f9a1b3c5d7`). `helix_migrations/` and `helix_alembic.ini` stay as they are. |
| `aof_alembic.ini` | New, from `hosting/aof_alembic.ini` |
| `config/agent-one-finance/**` | **Synced from the pack.** `connectors.yaml` stays ours. |
| `seed_data/aof_documents/**` | **Synced from the pack.** New: the documents service's sample files. `seed_data/helix_documents` stays. |
| `tests/agent_one_finance/**` | **Synced from the pack** |
| `app/requirements.txt` | Add `psycopg[binary,pool]>=3.2` and `mcp>=2.2,<3`. Everything else AOF needs is already listed, including `sqlalchemy[asyncio]` and `greenlet`. If pip reports a conflict with `fastmcp`, stop and report it. |
| `Dockerfile.helix` | Its contents become `hosting/Dockerfile.aof`, with the base image and pip mirror taken from `app/Dockerfile` |
| `.gitlab-ci-aof.yml` | Add `aof_migrations/`, `aof_alembic.ini` and `seed_data/aof_documents/` to its trigger paths |
| `ecs-task-definition-aof.json` | New, made from `ecs-task-definition-fobo.json` (section 6) |
| Agent One API (`api/`, `app/`) | The `/finance/api/*` route calls the AOF service (section 6). `api/routes/aof_cases.py` and `aof_notifications.py` keep working, because they call the synced `agent_one_finance` package. |
| `Dockerfile.fobo`, `ecs-task-definition-fobo.json`, `infrastructure/fobo-alb-rules.json`, the FOBO pipeline trigger | Removed after go-live |

## 3. The sync report

`aof_sync.py` writes `Skillgap/aof-sync-report.md`, and each repo gets `.aof-sync.json` (commit it).

| Label | Meaning | Action |
|---|---|---|
| `add`, `update`, `remove` | Changed in AOF; the office never edited the file | None |
| `keep-office` | Only the office changed it, or it is ours (`auth.js`, `connectors.yaml`, `session_bridge.py`) | None |
| `merge` | Both changed it, in different places; merged | Show the diff |
| `clash` | Both changed the same lines; marked `<<<<<<< office` … `>>>>>>> upstream` | Propose, settle after OK. The tool refuses to apply again while marks remain. |
| `differs` | First sync: the file matches no AOF release (the hand-converted console) | `--baseline` takes the pack's version |
| `office-only` | Not in AOF. Inside `src/app/finance`: a leftover, removed by `--baseline --prune`. Elsewhere: ours, left alone. | As stated |

The first sync also names the AOF release the office copy matches most closely.

## 4. The AOF database

1. Read the UAT AOF database's `alembic_version` table and its table list, and show them.
2. Then:
   - **An AOF id** (a file name in `fobotower-main/apps/backend/migrations/versions`): it upgrades as part of the
     deployment (section 6).
   - **No `alembic_version` table** (created by the deployment scripts): only if
     `alembic -c aof_alembic.ini check` reports no differences, run `alembic -c aof_alembic.ini stamp e7f9a1b3c5d7`
     once, with an OK.
   - **A `helix_migrations` id:** stop. Send the table list to the AOF team for a one-off step.

## 5. Settings for the AOF service

Set in the task definition. Each is described at the top of `agent_one_finance/config.py`.

| Setting | Value |
|---|---|
| `AOF_CONFIG_DIR`, `AOF_DOCUMENTS_DIR` | Set by `Dockerfile.aof` (`/app/config/agent-one-finance`, `/app/seed_data/aof_documents`) |
| `AOF_DATABASE_HOST`, `_PORT`, `_NAME`, `_USER`, `_PASSWORD` | Each from one key of the AOF database secret in Secrets Manager (`valueFrom: <secret arn>:<key>::`), as the other services' `DB_SECRET_NAME` secret is used |
| `AOF_TRUSTED_PROXY_SECRET` | A new secret, also given to the Agent One API |
| `AOF_IDENTITY_HEADER` | `X-AOF-User` (default) |
| `AOF_PROXY_SECRET_HEADER` | `X-AOF-Proxy-Secret` (default) |
| `AOF_LLM_ADAPTER` | As the FOBO backend has it today |
| `AOF_ENTITLEMENT_URL` | The entitlements service, if AOF reads roles and books from it |
| `AOF_CONSOLE_ORIGIN`, `AOF_CONSOLE_URL` | Agent One's address; the console URL ends in `/agentone/finance` |
| `AOF_ENV_NAME` | `uat` or `prod` |
| `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME` | As for the other agent services |
| `AOF_RUN_MODE`, `AOF_SCHEDULER` | Leave unset |

## 6. Hosting the AOF API next to the Agent One API

```
Browser ─> aos-frontend (Next.js, basePath /agentone)
             /api/finance/*  ─rewrite─>  Agent One API :8000  /finance/api/*
                                           checks the BAM sign-on (as for /sustagentapi)
                                           ─> AOF service :8300  /api/*    internal only
                                              with X-AOF-User and X-AOF-Proxy-Secret
```

- Step by step for both ways to run it: [`hosting/deploy-options.md`](hosting/deploy-options.md).
- AOF runs as **its own ECS service, the way the FOBO backend runs today**: own image, task definition, pipeline and
  health check.
- **The Agent One API stays the one front door**, so there is one sign-on check and no new public route. With
  `AOF_TRUSTED_PROXY_SECRET` set, AOF refuses any call that did not come through it.

| Piece | How |
|---|---|
| Image | `Dockerfile.helix` = `hosting/Dockerfile.aof`, with the base image and pip mirror from `app/Dockerfile`. Built by `.gitlab-ci-aof.yml` as `financeagent-aof-backend`, with the same shared build component and Wiz scan as `.gitlab-ci-api.yml`. |
| Task definition | `ecs-task-definition-aof.json`, copied from `ecs-task-definition-fobo.json`, then changed:<ul><li>family `agentone-aof-family`;</li><li>container `aof-backend`;</li><li>the image;</li><li>port 8300;</li><li>health check `curl -f http://localhost:8300/health`;</li><li>environment and secrets from section 5.</li></ul>Same roles, cluster, subnets and log settings as FOBO. |
| Service | One task in UAT and two in Prod. Scheduled cases and case runs are safe across tasks and workers: each schedule minute is claimed once, and each case is locked while it runs. |
| Network | A security group that lets only the Agent One API's tasks reach port 8300, behind an internal address (internal load balancer or service discovery). Set that address as `AOF_API_URL` on the Agent One API. |
| Agent One API route | Find what serves `/finance` today: search `api/` and `app/` for `"/finance"` and `mount(`. Then:<ul><li>**Mounted in-process:** replace the mount with the forwarding route in `hosting/aof_forward.py`, using our existing sign-on dependency.</li><li>**Already a forwarding route** (the SSO bridge): point it at `AOF_API_URL` and add both headers.</li></ul>Either way, AOF then runs in one place only. |
| Migrations | Before each deployment, a one-off task with the new image runs `alembic -c aof_alembic.ini upgrade head` |

Check after each deployment:

```bash
curl -s $AOF_API_URL/health                                            # from the Agent One API task
curl -s -H "Authorization: Bearer <token>" https://<host>/agentone/api/finance/me   # through the front door
```

`AOF_PATH_PREFIX=/finance` lets AOF also answer under `/finance/...`. It is for a load balancer rule that routes
`/finance/*` straight to AOF, and only if that layer itself adds `X-AOF-User` and `X-AOF-Proxy-Secret`. The browser
is never trusted to set identity.

## 7. Checks

- **aos-frontend**:
  - `npm run lint` and `npm run build:uat` both pass.
  - In UAT, screenshots of `/agentone/finance`, a case and a capability's "How it runs" tab, in light and dark.
  - The console's left-menu icons show.
- **aos-backend**:
  - The AOF tests pass. They need a Postgres with pgvector and a database name ending in `_test`; they empty
    every table, and refuse to run on any other database. They do not use our `tests/conftest.py`. Command:
    `AOF_TEST_DATABASE_URL=postgresql+asyncpg://<user>:<pw>@<host>:<port>/aof_test python -m pytest -q tests/agent_one_finance -o asyncio_mode=auto -o asyncio_default_fixture_loop_scope=session -o asyncio_default_test_loop_scope=session`
    (in a layout like ours: 298 passed and 10 skipped by design). If no such database is reachable, say so and skip
    this check.
  - `alembic -c aof_alembic.ini heads` shows one head, `e7f9a1b3c5d7`.
  - The AOF image builds (`docker build -f Dockerfile.helix .`), if Docker is available.
  - Inside it: `python -c "import agent_one_finance.web.main"`.

## 8. The prompts

### Prompt A: first time

> We are bringing Agent One Finance into aos-frontend and aos-backend from the pack in
> `Skillgap/fobotower-main/office/`. Read `Skillgap/fobotower-main/office/README.md` and follow its rules. Use a
> new branch `aof-sync` in both repos. Stop after each step and show me the result.
>
> 1. **Save our sign-on.** Before anything changes, show me how the current `src/app/finance/api/client.js` (and
>    `src/lib/sso.js`) add the BAM token to AOF calls.
> 2. **Dry run.** From `Skillgap`, run `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main` and show me
>    `aof-sync-report.md`. Then:
>    - List the files outside `src/app/finance` that import from it. Expect `FinanceCasesWidget.jsx`.
>    - List the leftovers from README section 2, saying for each whether anything else imports it.
>    - For each backend `differs`, `merge` or `clash`, show me the diff.
> 3. **Apply.** Once I agree, run it with `--apply --baseline --prune`. Show me the report and `git status` of both
>    repos.
> 4. **Wire aos-frontend** (README section 2):
>    - `auth.js`, using the sign-on from step 1;
>    - the `.env` files, the lint ignore and `--aof-height`;
>    - the sidebar entry and the widget imports;
>    - remove the leftovers I approve.
> 5. **Wire aos-backend** (README sections 2, 5 and 6):
>    - `app/requirements.txt`, `aof_alembic.ini`, `Dockerfile.helix` and the `.gitlab-ci-aof.yml` triggers;
>    - `ecs-task-definition-aof.json`;
>    - show me what serves `/finance` in the Agent One API today, and propose the forwarding change;
>    - list the secrets and settings DevOps must create: names only, no values.
>
>    Deploy nothing.
> 6. **Database** (README section 4). Read UAT's `alembic_version` and table list and show me. Run nothing against
>    the database.
> 7. **Check** (README section 7) and report the results.
> 8. **Commit** in each repo, including `.aof-sync.json`. Summarise:
>    - what was replaced, merged, kept and removed;
>    - the wiring;
>    - the hosting files;
>    - what DevOps must do;
>    - the check results.
>
>    Stop; I will raise the merge requests.

### Prompt B: every later release

> Update Agent One Finance from the pack in `Skillgap/fobotower-main/office/`, following its README. Use a new branch
> `aof-sync-<date>` in both repos.
>
> 1. From `Skillgap`, run `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main` and show me the report.
> 2. Once I agree, run it with `--apply`.
>    - For each `clash`, show me the marked lines, propose how to settle them, and wait for my OK.
>    - Then run it again until it applies cleanly.
> 3. Add any packages the report lists. If `aof_migrations` changed, say so; it runs with the next deployment.
> 4. Run the checks in README section 7.
> 5. Commit with `.aof-sync.json` and summarise as before.

## 9. For the AOF team (this repository)

- After any console change, run `cd apps/web && npm run office:build`.
- After any change to a synced backend file, run `python3 office/build_history.py`.
- Commit the results with the change. Tests fail if either is out of date.
