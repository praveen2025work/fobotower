# Agent One Finance in aos-frontend and aos-backend: the conversion guide

**Final version, 9 Oct 2026. This is the only guide.** Earlier migration, update and conversion pages are in
[`../archive/`](../archive/README.md), for the record only. Do not use them.

**For:** office Claude Code, working in the `Skillgap` workspace with the person who runs it. It covers:

1. bringing AOF from `fobotower-main` into `aos-frontend` and `aos-backend`, the same way on every release;
2. hosting the AOF API on AWS next to the Agent One API.

---

## For the person: what to do

1. Download `main` of `praveen2025work/fobotower` as a zip and unpack it as `Skillgap/fobotower-main`.
2. First time only, also download `https://github.com/praveen2025work/fobotower/archive/dbaac6f.zip` and unpack
   it as `Skillgap/fobotower-base`. That is the backend version the office last copied.
3. Paste the prompt in [section 9](#9-the-prompts) into office Claude: the first-time prompt, or the update prompt
   after that. Approve each step it shows you.

---

## 1. Rules for office Claude

- **Never convert, restyle or rewrite AOF code by hand.** The console is converted once, in `fobotower-main`
  (`apps/web/office/convert.mjs`). The result is in `fobotower-main/office/aos-frontend/`, already in
  `aos-frontend`'s shape: Next.js App Router, JSX, Tailwind-independent styles. A test there fails if that
  folder is out of date.
- **Copy with the sync tool only:** `python3 fobotower-main/office/aof_sync.py`. It merges, so office changes
  are kept.
- **Work on a branch.** Never touch the main branch, a deployment, a database or a secret without the person's
  OK.
- **Stop after each numbered step**, show the result, and wait.
- If something does not work, report what and why. Do not work around it by editing AOF code.

## 2. What goes where

| From `fobotower-main` | To | Owned by |
|---|---|---|
| `office/aos-frontend/src/app/finance/**` | `aos-frontend/src/app/finance/**`: the `/finance` pages, and the console code in the private folder `_aof/` | AOF (synced) |
| `apps/backend/agent_one_finance/**` | `aos-backend/agent_one_finance/**` | AOF (synced) |
| `apps/backend/migrations/**` | `aos-backend/aof_migrations/**` | AOF (synced) |
| `config/agent-one-finance/**` | `aos-backend/config/agent-one-finance/**` | AOF (synced), except `connectors.yaml` |
| `apps/backend/seed_data/aof_documents/**` | `aos-backend/seed_data/aof_documents/**` | AOF (synced) |
| `apps/backend/tests/agent_one_finance/**` | `aos-backend/tests/agent_one_finance/**` | AOF (synced) |
| `office/hosting/*` | `aos-backend` (section 8), copied once | Office |
| `apps/backend/pyproject.toml` dependencies | `aos-backend/app/requirements.txt` (the sync report lists what is missing) | Office |

These files are the office's own. The sync never overwrites them:

- `src/app/finance/_aof/office/auth.js`: the sign-on headers for AOF calls;
- `config/agent-one-finance/connectors.yaml`: the office's connection settings;
- `agent_one_finance/session_bridge.py`: the office's session bridge.

These are not AOF, and the sync never reads or writes them:

- `src/components/financeagent/` and `/financeagent`: Agent One's own Finance Agent;
- the rest of `aos-frontend` and `aos-backend`;
- `/fobo`, `Dockerfile.fobo`: the original FOBO app, retired after go-live.

## 3. How the console fits aos-frontend

This was tested in a Next.js app set up like aos-frontend:

- Next.js 16.1.1, built with `next build --webpack`;
- `basePath: "/agentone"`;
- React 19.2.3, Tailwind 4 with `tailwind.config.js` (`darkMode: ["class"]`);
- next-themes, lucide-react 0.562, eslint-config-next.

The results:

- the build passes and lint is clean;
- every page loads with no browser errors;
- links and the left menu go to `/agentone/finance/...`;
- the icons show;
- the console follows Agent One's light and dark theme;
- Agent One's own pages are unchanged.

| Part | Detail |
|---|---|
| Routes | `/finance`, `/finance/inbox`, `/finance/capabilities`, `/finance/capabilities/[id]`, `/finance/capabilities/[id]/groups/[group]`, `/finance/cases/[caseId]`, `/finance/authoring`, `/finance/operations`, `/finance/audit`, `/finance/connectors` |
| Frame | `src/app/finance/layout.jsx` wraps the pages in `_aof/office/FinanceShell.jsx`: the console's query cache, its left menu and top bar |
| Styles | `_aof/finance.css`, compiled in `fobotower-main` and scoped to `#aof-root`; no change to Agent One's Tailwind set-up |
| Height | Fills the viewport by default. Under Agent One's header, set `--aof-height` (for example `calc(100vh - 64px)`) on an element around it. |
| Packages | `@tanstack/react-query`, `clsx`, `yaml`, `lucide-react`, `next-themes`. aos-frontend already has them all. |
| Sign-on | `_aof/office/auth.js` returns the headers every AOF call needs: the same BAM token the rest of aos-frontend sends to the Agent One API |
| API address | `NEXT_PUBLIC_AOF_API=/agentone/api/finance` in `.env.development`, `.env.uat` and `.env.production`. Next.js rewrites `/api/finance/*` to the Agent One API (section 8). |
| Lint | Add `{ ignores: ["src/app/finance/_aof/**"] }` to `eslint.config.mjs`. That code is linted and type-checked in `fobotower-main`, in TypeScript. |

## 4. The workspace

```
Skillgap/
  fobotower-main/       the latest download of main, replaced on every update
  fobotower-base/       first time only: the backend version the office copied last (dbaac6f)
  aos-frontend/         repo
  aos-backend/          repo
  aof-sync.json         optional: only if a folder name differs from section 2
  aof-sync-base/        kept by the sync tool between runs. Do not delete.
  aof-sync-report.md    written by every run
```

Each repo gets `.aof-sync.json`, recording what was synced and when. Commit it with the update.

## 5. Reading the sync report

| In the report | Meaning | What to do |
|---|---|---|
| `add`, `update`, `remove` | Changed in AOF; the office never edited the file | Nothing |
| `keep-office` | Only the office changed it, or it is an office file | Nothing |
| `merge` | Both changed it, in different places; merged | Show the diff |
| `clash` | Both changed the same lines; marked `<<<<<<< office` … `>>>>>>> upstream` | Show both, propose, settle after the person's OK. The next run refuses to apply while marks remain. |
| `differs` | First sync only: different, with no common base | Review; `--baseline` takes the AOF version |
| `office-only` | Not in AOF. In `src/app/finance` it is a leftover of the hand conversion; elsewhere it is the office's own | `--baseline --prune` removes leftovers in `src/app/finance` only |
| Packages to add | AOF needs a Python package that `app/requirements.txt` lacks | Add it |

## 6. The AOF database

The office has `helix_migrations` (18 versions, an older lineage) and removed `aof_migrations`. The AOF code
needs AOF's own history: 25 versions, head `e7f9a1b3c5d7`.

1. Read the UAT AOF database's `alembic_version` table and its list of tables. Show them to the person.
2. Then:
   - **An AOF id** (a file name in `fobotower-main/apps/backend/migrations/versions`): run
     `alembic -c aof_alembic.ini upgrade head`.
   - **No `alembic_version` table** (created by deployment scripts): only if `alembic -c aof_alembic.ini check`
     reports no differences, run `alembic -c aof_alembic.ini stamp e7f9a1b3c5d7` once.
   - **A `helix_migrations` id:** stop. The person sends the table list to the AOF team for a one-off step.
3. From then on, every deployment runs `alembic -c aof_alembic.ini upgrade head` before the new service starts
   (section 8).

## 7. Settings for the AOF service

The defaults assume the `fobotower-main` folder layout, so these must be set:

- `AOF_CONFIG_DIR=/app/config/agent-one-finance`;
- `AOF_DOCUMENTS_DIR=/app/seed_data/aof_documents`.

`Dockerfile.aof` sets both.

| Setting | Value |
|---|---|
| Database | `AOF_DATABASE_HOST`, `AOF_DATABASE_PORT`, `AOF_DATABASE_NAME`, `AOF_DATABASE_USER`, `AOF_DATABASE_PASSWORD`, each from one key of the database secret (or one `AOF_DATABASE_URL`) |
| `AOF_TRUSTED_PROXY_SECRET` | From the secrets store; the same value on the Agent One API. AOF then refuses any call that did not come through it. |
| `AOF_IDENTITY_HEADER` | `X-AOF-User` (the default) |
| `AOF_PROXY_SECRET_HEADER` | `X-AOF-Proxy-Secret` (the default) |
| `AOF_LLM_ADAPTER` | The office's model adapter (as set today for the FOBO backend) |
| `AOF_ENTITLEMENT_URL` | The entitlements service, if AOF reads roles and books from it |
| `AOF_CONSOLE_ORIGIN`, `AOF_CONSOLE_URL` | Agent One's address; the console URL ends in `/agentone/finance` |
| `AOF_ENV_NAME` | `uat` or `prod` |
| `AOF_RUN_MODE`, `AOF_SCHEDULER` | Leave unset (background runs, scheduler on) |
| `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME` | As for the other agent services |

Every setting is described at the top of `agent_one_finance/config.py`.

## 8. Hosting the AOF API on AWS, next to the Agent One API

**The design: the Agent One API stays the one front door.**

```
Browser ──> aos-frontend (Next.js, /agentone)
              /api/finance/*  ── rewrite ──>  Agent One API (8000)  /finance/api/*
                                                 checks the BAM sign-on, then calls
                                                 ──> AOF service (8300)  /api/*   (internal only)
                                                       with X-AOF-User and X-AOF-Proxy-Secret
```

- AOF runs as **its own ECS service, the way the FOBO backend runs today**: its own image, task definition,
  pipeline and health check.
- Only the Agent One API can reach it, so there is **one sign-on check** and no new public route.
- The aos-frontend rewrite does not change: `/api/finance/*` already goes to `{API_URL}/finance/api/*`.

What to build, all by copying what already exists for the FOBO backend and the Agent One API:

| Piece | How |
|---|---|
| Image | `fobotower-main/office/hosting/Dockerfile.aof` becomes the contents of `Dockerfile.helix`. Take the base image and pip mirror from `app/Dockerfile`. Copy `office/hosting/aof_alembic.ini` to `aos-backend/aof_alembic.ini`. |
| Pipeline | `.gitlab-ci-aof.yml`, same shared build component and Wiz scan as `.gitlab-ci-api.yml`. Image `financeagent-aof-backend`. Add `aof_migrations/`, `aof_alembic.ini` and `seed_data/aof_documents/` to its trigger paths. |
| Task definition | Copy `ecs-task-definition-fobo.json` to `ecs-task-definition-aof.json`, then change:<ul><li>family `agentone-aof-family`;</li><li>container `aof-backend`;</li><li>the image;</li><li>port 8300;</li><li>health check `curl -f http://localhost:8300/health`;</li><li>environment and secrets from section 7.</li></ul>Same roles, cluster, subnets and log settings as FOBO. |
| Service | One task in UAT and two in Prod. Scheduled cases and case runs are safe across tasks and workers: each schedule minute is claimed once, and each case is locked while it runs. |
| Network | A security group that lets only the Agent One API's tasks reach port 8300. Give it an internal address (an internal load balancer or service discovery name) and set `AOF_API_URL` on the Agent One API to it. |
| Agent One API route | `/finance/api/*` checks the sign-on, then calls `AOF_API_URL` + `/api/*`, adding `X-AOF-User` (the signed-in bank id) and `X-AOF-Proxy-Secret`. If the Agent One API already serves `/finance/api` (the SSO bridge), point that route at the service. Otherwise use `fobotower-main/office/hosting/aof_forward.py` as the reference. Either way, AOF then runs in one place only: remove any in-process mount of AOF from the Agent One API. |
| Migrations | Before each deployment, run `alembic -c aof_alembic.ini upgrade head` as a one-off task with the new image (section 6). |

Checks after each deployment:

```bash
# from inside the Agent One API task (AOF is internal only)
curl -s $AOF_API_URL/health
# through the front door, signed in, from the browser or with a test token
curl -s -H "Authorization: Bearer <token>" https://<agent one host>/agentone/api/finance/me
```

**Other routing (only if the bank's load balancer adds the signed-in identity itself).** AOF can also answer
under a path: set `AOF_PATH_PREFIX=/finance`, and a load balancer rule `/finance/*` → the AOF target group serves
`/finance/api/...` and `/finance/health`. Use this only if that layer sets `X-AOF-User` and
`X-AOF-Proxy-Secret`. The browser must never be trusted to set identity.

After go-live, retire FOBO: `Dockerfile.fobo`, `ecs-task-definition-fobo.json`, `infrastructure/fobo-alb-rules.json`,
the FOBO pipeline trigger, and `/fobo` in aos-frontend.

## 9. The prompts

### First time (once)

> We are bringing Agent One Finance into aos-frontend and aos-backend, and hosting the AOF API on AWS.
> Read `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md` and follow its rules
> (section 1). Use a new branch `aof-sync` in both repos. Stop after each step and show me the result.
>
> 1. **Dry run.** From `Skillgap`, run
>    `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main --base-from fobotower-base` and show me
>    `aof-sync-report.md`. Then:
>    - List any file outside `src/app/finance` that imports from it (for example
>      `src/components/finance/FinanceCasesWidget.jsx`).
>    - List what the hand conversion added outside `src/app/finance`:
>      - the `ui.tsx` split in `src/components/ui/`;
>      - `useIsPhone.js` and `useStickyBottom.js` in `src/components/financeagent/layout/`;
>      - `docs/helix-ui-reference/`.
>
>      For each, say whether anything else imports it.
>    - For each backend `differs`, `clash` or `office-only` file, show me the diff and say whether it is our
>      change to keep.
> 2. **Apply.** Once I agree, run the same command with `--apply --baseline --prune`. Show me the report and
>    `git status` for both repos.
> 3. **aos-frontend wiring (guide section 3).**
>    - Port our BAM sign-on into `src/app/finance/_aof/office/auth.js`. It must send the same token our other
>      API calls send.
>    - Set `NEXT_PUBLIC_AOF_API=/agentone/api/finance` in the three `.env` files.
>    - Add the lint ignore line to `eslint.config.mjs`.
>    - Re-point the importers from step 1 to `src/app/finance/_aof/...`.
>    - Remove the leftovers I approve.
>    - Check the Finance menu entry goes to `/finance`.
>    - Set `--aof-height` if the page has a fixed header.
> 4. **AOF database (guide section 6).** Read UAT's `alembic_version` and table list and show me. Run nothing
>    against the database until I say which case applies.
> 5. **Hosting (guide sections 7 and 8).**
>    - Add the packages the report lists to `app/requirements.txt`.
>    - Copy `aof_alembic.ini`.
>    - Replace the contents of `Dockerfile.helix` with `office/hosting/Dockerfile.aof`, using the base image and
>      pip mirror from `app/Dockerfile`.
>    - Update `.gitlab-ci-aof.yml` triggers.
>    - Create `ecs-task-definition-aof.json` from the FOBO one.
>    - Show me how the Agent One API serves `/finance/api` today. Then propose the change that makes it call
>      the AOF service, with the sign-on check and both headers (reference: `office/hosting/aof_forward.py`).
>    - List the secrets and settings DevOps must create (section 7), with names only, no values.
>
>    Do not deploy anything.
> 6. **Check.**
>    - aos-frontend: `npm run lint` and `npm run build:uat`.
>    - aos-backend: `pytest -q tests/agent_one_finance`, `alembic -c aof_alembic.ini heads` (one head,
>      `e7f9a1b3c5d7`), and a local Docker build of the AOF image, if Docker is available here.
> 7. **Commit** in each repo, including `.aof-sync.json`. Summarise for me:
>    - what was replaced, merged, kept and removed;
>    - the wiring;
>    - the hosting files;
>    - what DevOps must do;
>    - the check results.
>
>    Stop there; I will raise the merge requests.

### Every update after that

> Update Agent One Finance from `Skillgap/fobotower-main` with the sync tool, following
> `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md`. Use a new branch
> `aof-sync-<date>` in both repos.
>
> 1. From `Skillgap`, run `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main` and show me the
>    report.
> 2. Once I agree, run it with `--apply`.
>    - For each `clash`, show me the marked lines, propose how to settle them, and wait for my OK.
>    - Then run it again until it applies cleanly.
> 3. Add any packages the report lists. If `aof_migrations` changed, tell me; the migration runs as part of the
>    next deployment.
> 4. Run the checks from step 6 of the first-time prompt.
> 5. Commit with `.aof-sync.json` and summarise as before.

## 10. For the AOF team (in `fobotower-main`)

1. After any console change, run `cd apps/web && npm run office:build` and commit `office/aos-frontend`.
   `npm test` fails if you forget.
2. The conversion lives in `apps/web/office/convert.mjs` and `apps/web/office/templates/`:
   - `router.js` and `FinanceShell.jsx`;
   - `theme.js`, which follows next-themes;
   - `auth.js`, the office-owned starting point.
3. The sync tool is `office/aof_sync.py`; its tests are in `apps/backend/tests/agent_one_finance/test_office_sync.py`.
4. The hosting templates are in `office/hosting/`.
