# Deployment

How to run the FOBO console on a shared server (a demo or UAT box), rather than
on a developer's machine. For local development, see the README.

## Read this first: it is not production-ready

- **There is no real login.** `fobo/web/auth.py` is a stub: outside dev mode,
  every request acts as the built-in caller `praveen` (roles FO and PC). Anyone
  who can reach the API can approve adjustments as that person. Swapping in
  BAM and the entitlement service touches only that module, but until then keep
  a deployment on a restricted network, for demos and UAT only.
- **It seeds demo data.** The first request loads the illustrative scenario in
  `seed_data/` into an empty database.
- **It isn't connected to CATS or MOTIF yet.** Breaks come from the seed data,
  and "Post to MOTIF" is recorded in this app's database only. The source
  adapters are later-phase work.

## What you deploy

| Part | What runs | Port (default) |
|---|---|---|
| Database | Postgres 16 with the `pgvector` extension | 5432 (5433 in `docker-compose.yml`) |
| Backend | `uvicorn fobo.web.main:app` from `apps/backend` | 8100 |
| Console | `next start` from `apps/console`, after `next build` | 3100 |

The backend reads its playbook and workflow files from `config/` by path
relative to the repo, so deploy the **whole repo checkout**, not just
`apps/backend`.

## Configuration

Backend (environment variables):

| Variable | Required | Meaning |
|---|---|---|
| `FOBO_DATABASE_URL` | yes | `postgresql+asyncpg://user:password@host:port/db`. Default is the local dev database. |
| `FOBO_CONSOLE_ORIGINS` | yes | Comma-separated URLs the console is served from, e.g. `https://fobo-uat.example.internal`. Anything else is refused by CORS. |
| `FOBO_ENV` | no | `dev` turns on the **Act as** switch (acting as another user). **Leave it unset on a shared server**, except for a four-eyes demo. |
| `FOBO_REASONER` | no | `none` (default in the workflow file), `session_service`, or `direct`. `direct` is for local development only. |
| `FOBO_SESSION_SERVICE_URL`, `FOBO_SESSION_SERVICE_TOKEN`, `FOBO_SESSION_SKILL_ID` | with `session_service` | The session service the reasoner calls. See `docs/integration/session-service-contract.md`. |
| `FOBO_MCP_URL`, `FOBO_MCP_TOKEN` | with `session_service` | This backend's MCP address and token, passed to the session so the model can query the graph. |
| `FOBO_PLAYBOOK_PATH`, `FOBO_WORKFLOW_PATH` | no | Use a different playbook or workflow file than the ones in `config/`. |

Keep tokens and the database password in your secret store or the service's
environment. Never commit them.

Console (set **at build time**, because Next.js bakes it into the bundle):

| Variable | Meaning |
|---|---|
| `NEXT_PUBLIC_API_BASE` | The backend's URL as the **browser** sees it, e.g. `https://fobo-uat-api.example.internal`. Default `http://localhost:8100`. |

## First deployment

### 1. Database

Create a Postgres 16 database and a user that owns it. The first migration runs
`CREATE EXTENSION vector`. If the app's user can't create extensions, ask the
DBA to run this once in that database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

For a single box, the repo's compose file also works:

```bash
docker compose up -d postgres
```

### 2. Backend

From `apps/backend`, with Python 3.12:

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -e .
```

```bash
.venv/bin/alembic upgrade head
```

Migrations use `FOBO_DATABASE_URL`, the same database as the app, so set it
before this step. Then start the API:

```bash
.venv/bin/uvicorn fobo.web.main:app --host 0.0.0.0 --port 8100
```

Leave out `--reload` on a server. Run it under your process manager
(systemd, a Windows service, or a container) so it restarts on failure, with
the variables above in its environment.

On a **Windows server**, use `.venv\Scripts\` instead of `.venv/bin/`, and add
`--loop asyncio:SelectorEventLoop` to the `uvicorn` command. psycopg, which the
LangGraph checkpointer uses, can't run on Windows' default event loop.

Check it's up:

```bash
curl http://localhost:8100/health
```

### 3. Console

From `apps/console`, with Node 20+:

```bash
npm ci
```

```bash
NEXT_PUBLIC_API_BASE=https://fobo-uat-api.example.internal npm run build
```

```bash
npm run start
```

`npm run start` serves on port 3100. Run it under the same process manager.

### 4. In front of both

Put both behind your usual reverse proxy or load balancer with TLS. The
console's public URL must be listed in `FOBO_CONSOLE_ORIGINS`, and the API's
public URL must match the `NEXT_PUBLIC_API_BASE` the console was built with.

### 5. Smoke test

Open the console URL. The board should show the recs and the event status
strip. If it shows an error instead, check `NEXT_PUBLIC_API_BASE`, the
proxy, and `FOBO_CONSOLE_ORIGINS`, in that order.

## Updating

1. Back up the database.
2. `git pull` the release you're deploying.
3. Backend: `.venv/bin/pip install -e .`, then `.venv/bin/alembic upgrade head`, then restart the service.
4. Console: `npm ci`, `npm run build` (with `NEXT_PUBLIC_API_BASE` set), then restart.
5. Run the smoke test.

Always migrate **before** restarting the backend: new code expects the new
tables.

## Resetting the demo scenario

To undo every decision and chat message and start the scenario again, clear
the app tables and checkpoints (the README has the exact `TRUNCATE` command).
The next request reseeds.
