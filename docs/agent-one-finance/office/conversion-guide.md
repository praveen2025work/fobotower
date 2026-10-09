# Agent One Finance in the office: conversion guide

**For:** you and office Claude Code, bringing Agent One Finance (AOF) from this repository into the
office repos `aos-frontend` and `aos-backend`, and hosting the AOF service on AWS.

**This is the only guide.** It replaces every earlier migration, update and conversion page (now in
[`../archive/`](../archive/README.md), for the record only).

## 1. The rule: the conversion happens here, not in the office

Each earlier update was converted by hand in the office: TSX to JSX, Vite routes to Next.js routes,
Tailwind 3 to 4. That lost the styles and the menu icons, and missed the newest screens.

Now the conversion is one script in this repository, run the same way every time:

- `apps/web/office/convert.mjs` turns the console into the office's shape and commits the result in
  [`office/aos-frontend/`](../../../office/aos-frontend).
- A test fails if that folder is not up to date, so the office copy always matches the console.
- `office/aof_sync.py` copies it, and the backend, into the office repos. It keeps the office's own
  changes with a three-way merge.

**Office Claude never converts code.** It runs the sync, settles anything the sync marks, builds, tests
and reports.

## 2. What goes where

| Upstream (this repository) | Office | How |
|---|---|---|
| `apps/web` (Vite, TSX, Tailwind 3) | `aos-frontend/src/app/finance/**` (Next.js pages) and `aos-frontend/src/components/financeagent/**` | Converted here into `office/aos-frontend/src/…`, then copied by `aof_sync.py` |
| `apps/backend/agent_one_finance` | `aos-backend/agent_one_finance` | Copied by `aof_sync.py`; office changes are kept |
| `apps/backend/migrations` | `aos-backend/aof_migrations`, or the office's folder name | Copied by `aof_sync.py`; set the name in `aof-sync.json` (section 5) |
| `config/agent-one-finance` | `aos-backend/config/agent-one-finance` | Copied by `aof_sync.py`; `connectors.yaml` stays the office's |
| `apps/backend/pyproject.toml` dependencies | `aos-backend/requirements.txt` | The sync report lists what is missing; add it by hand |

The original FOBO app is not part of AOF and is never copied.

## 3. How the converted console fits Agent One

This was checked in a Next.js 16.1.1, React 19 and Tailwind CSS 4 app laid out like Agent One:

- the build passes;
- every page loads with no browser errors;
- links between pages work;
- the left-menu icons show;
- light and dark themes both work;
- Agent One's own pages look exactly as before.

| Part | In the office |
|---|---|
| Routes | `/finance` (Overview), `/finance/inbox`, `/finance/capabilities`, `/finance/capabilities/[id]`, `/finance/capabilities/[id]/groups/[group]`, `/finance/cases/[caseId]`, `/finance/authoring`, `/finance/operations`, `/finance/audit`, `/finance/connectors`. Each is a small `page.jsx` that loads the console's page in the browser. |
| Frame | `src/app/finance/layout.jsx` wraps every finance page in `FinanceShell`: the console's query cache, its own left menu and top bar, and the theme. |
| Navigation | `financeagent/office/router.js` gives the console's links the Next.js router. To move the console from `/finance`, change `FINANCE_BASE` there. |
| Styles | `financeagent/finance.css` is compiled here and scoped to `#aof-root`. It does not use, need or change Agent One's Tailwind set-up, and Agent One's styles do not change the console. |
| Height | The console fills the viewport by default. Under Agent One's header, set `--aof-height` on a parent element, for example `--aof-height: calc(100vh - 64px)`. |
| Icons | `lucide-react`. The icons used are listed in `office/aos-frontend/aof-frontend.json` (`icons`). The office's version must have them all (check in section 6). |
| Packages | `@tanstack/react-query`, `clsx`, `yaml`, `lucide-react`. The sync report lists any that `aos-frontend` lacks. |
| Settings | `NEXT_PUBLIC_AOF_API`: where the AOF API is (default `/api`). `NEXT_PUBLIC_AOF_TRACE_URL` is optional. |
| Identity | One header, `X-AOF-User` (or the `AOF_IDENTITY_HEADER` the API is set to), added by the single sign-on proxy. The console sends no identity itself. |
| Agent One menu | Add a Finance link to `/finance` in Agent One's own navigation. That file is Agent One's, so the sync never touches it. |

## 4. The workspace

```
Skillgap/
  fobotower-main/       the latest download of this repository (main), replaced on every update
  aos-frontend/         office repo
  aos-backend/          office repo
  aof-sync.json         optional: the office's folder names and kept files (section 5)
  aof-sync-base/        kept by the sync tool: what upstream looked like at the last sync. Do not delete.
  aof-sync-report.md    written by every run
```

Each office repo also gets `.aof-sync.json`: what was synced and when. Commit it.

## 5. The office settings file (`Skillgap/aof-sync.json`)

Only needed where the office differs from the defaults. A complete example:

```json
{
  "frontend": {
    "repo": "aos-frontend",
    "roots": [
      ["office/aos-frontend/src/components/financeagent", "src/components/financeagent"],
      ["office/aos-frontend/src/app/finance", "src/app/finance"]
    ],
    "keep": [],
    "owned": ["src/components/financeagent", "src/app/finance"]
  },
  "backend": {
    "repo": "aos-backend",
    "roots": [
      ["apps/backend/agent_one_finance", "agent_one_finance"],
      ["apps/backend/migrations", "helix_migrations"],
      ["config/agent-one-finance", "config/agent-one-finance"]
    ],
    "keep": ["config/agent-one-finance/connectors.yaml", "agent_one_finance/session_bridge.py"],
    "owned": []
  }
}
```

- **`roots`**: upstream folder → office folder.
- **`keep`**: office files the sync must never overwrite. Every other office change is merged.
- **`owned`**: folders that hold only AOF. Files there that upstream does not have are leftovers of an
  earlier conversion.

## 6. First time: replace the earlier hand conversion (once)

1. **Get the code.**
   - Download `main` of this repository as a zip and unpack it as `Skillgap/fobotower-main`.
   - Also download the version the office last copied the backend from, as the base for merging
     office edits: `https://github.com/praveen2025work/fobotower/archive/dbaac6f.zip`, unpacked as
     `Skillgap/fobotower-base`.
2. **Write `aof-sync.json`** with the office's migrations folder name and kept files (section 5).
3. **Paste the first-time prompt below** into office Claude.

> We are bringing Agent One Finance into aos-frontend and aos-backend with the upstream sync tool.
> Read `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md` first and follow it.
> Do not convert, restyle or rewrite any upstream file yourself. If something does not work, tell me
> what and why.
>
> Work on a new branch `aof-sync` in both repos. Do not touch the main branch, any deployment, database
> or secret. Stop after each step and show me the result.
>
> 1. **Dry run.** From `Skillgap`, run
>    `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main --base-from fobotower-base`
>    and show me `aof-sync-report.md`.
>    - Frontend `differs` are the earlier hand conversions; they will be replaced.
>    - Frontend `office-only` files in `src/components/financeagent` or `src/app/finance` are leftovers
>      of that conversion (for example the `ui/` split).
>    - For each frontend leftover, say whether any Agent One file imports it. Search outside those two
>      folders.
>    - For each backend `differs`, `clash` or `office-only` file, show me the diff and say whether it is
>      an office change to keep. If it is, tell me so I can add it to `keep` in `aof-sync.json`.
> 2. **Apply.** Once I agree, run the same command with `--apply --baseline --prune`, then show the
>    report and `git status` for both repos.
> 3. **Packages and settings.**
>    - Add the packages the report lists. Use the versions given, from our registry.
>    - Check that our `lucide-react` has every icon in `fobotower-main/office/aos-frontend/aof-frontend.json`
>      (`icons`): `node -e "const l=require('lucide-react');const m=require('../fobotower-main/office/aos-frontend/aof-frontend.json').icons.filter(i=>!l[i]);console.log(m.length?'missing: '+m:'all icons present')"`,
>      run inside aos-frontend.
>    - Set `NEXT_PUBLIC_AOF_API` the way Agent One reaches the AOF API.
>    - Add a Finance entry to `/finance` in Agent One's menu, the way the other entries are written.
>    - If Agent One has a fixed header, set `--aof-height` (guide section 3).
> 4. **Check.**
>    - aos-frontend: run `npm run build` and `npm run lint` (if there is one).
>    - aos-backend: run `pytest -q` (if there are tests) and `alembic -c <our AOF alembic ini> heads`.
>      Expect one head.
>    - Run both against UAT. Give me screenshots of `/finance`, a case and a capability's
>      "How it runs" tab, and confirm the left-menu icons show.
> 5. **Commit** in each repo, including `.aof-sync.json`. Summarise:
>    - what was replaced, merged, kept and removed;
>    - the packages added;
>    - the check results.
>
>    Stop there; I will raise the merge requests.

## 7. Every update after that

1. Replace `Skillgap/fobotower-main` with a new download of `main`.
2. Paste this prompt:

> Update Agent One Finance from upstream with the sync tool, as
> `Skillgap/fobotower-main/docs/agent-one-finance/office/conversion-guide.md` section 7 says. Use a new
> branch `aof-sync-<date>` in both repos. Never convert or rewrite upstream files yourself.
>
> 1. Run `python3 fobotower-main/office/aof_sync.py --upstream fobotower-main` from `Skillgap` and show
>    me the report.
> 2. Once I agree, run it again with `--apply`.
>    - For each `clash`, show me the marked lines, propose how to settle them, and wait for my OK.
>    - Then run the sync again until it applies cleanly.
> 3. Add any packages the report lists, and any new `requirements.txt` lines.
> 4. Run the checks from section 6 step 4.
> 5. Commit in each repo with `.aof-sync.json`, and summarise as in section 6 step 5.

What the report means:

| In the report | Meaning | What to do |
|---|---|---|
| `add`, `update`, `remove` | Upstream changed a file the office never edited | Nothing |
| `keep-office` | Only the office changed it | Nothing |
| `merge` | Both changed it, in different places; merged | Look at the diff |
| `clash` | Both changed the same lines; marked `<<<<<<< office` … `>>>>>>> upstream` | Settle by hand. The next run refuses to apply until no marks are left. |
| `office-only` | The office's own file | Nothing |
| Packages to add | Upstream needs a package the office has not listed | Add it |

## 8. The AOF service on AWS

`aos-backend` runs AOF as its own service next to the existing API (8000). The AOF database (Postgres
with pgvector) already exists.

| | |
|---|---|
| Image | Python 3.12. Install `requirements.txt`; it must include `sqlalchemy[asyncio]` **and** `greenlet>=3.0`. Without `greenlet` the image builds but fails at the first database call. |
| Start | `uvicorn agent_one_finance.web.main:app --host 0.0.0.0 --port 8300` |
| Health check | `GET /health` on 8300 |
| Database | `AOF_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>`, from the secrets store |
| Migrations | Before each deployment, a one-off task: `alembic -c <AOF alembic ini> upgrade head`. The first migration runs `CREATE EXTENSION IF NOT EXISTS vector`; on RDS the user needs `rds_superuser` that first time, or a DBA creates the extension beforehand. |
| Settings (names) | `AOF_CONFIG_DIR` (the folder with `config/agent-one-finance`), `AOF_LLM_ADAPTER` (`agent_sdk` in the office), `AOF_IDENTITY_HEADER`, `AOF_TRUSTED_PROXY_SECRET` and `AOF_PROXY_SECRET_HEADER`, `AOF_CONSOLE_ORIGIN` and `AOF_CONSOLE_URL` (Agent One's address), `AOF_ENTITLEMENT_URL`, `AOF_ENV_NAME` (`uat`, `prod`), `AOF_RUN_MODE`, `AOF_SCHEDULER`, `AOF_REPORTS_STORE`, `AOF_DOCUMENTS_DIR`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME`. The meaning of each is in `agent_one_finance/config.py`. |
| Frontend to API | Agent One reaches the service either through its proxy or rewrites (then `NEXT_PUBLIC_AOF_API=/api/finance` or similar), or directly (the service's URL). Either way, the single sign-on layer adds the identity header, and only it can: set `AOF_TRUSTED_PROXY_SECRET`. |

Checks after each deployment:

```bash
curl -s https://<aof-service>/health
curl -s -H "X-AOF-User: <a test user>" https://<aof-service>/api/me
```

## 9. Changing the conversion (upstream only)

In this repository:

1. Run `cd apps/web && npm run office:build` after any console change.
2. Commit `office/aos-frontend` with the change. `npm test` fails if you forget.

To change how the console is converted, edit `apps/web/office/convert.mjs` and its templates
(`office/templates/router.js`, `FinanceShell.jsx`). Then check the result in a Next.js app like Agent
One's, as in section 3.
