# Opening Agent One Finance on a Mac or phone

## 1. Read-only snapshot (no setup)

A snapshot is the real web app over data recorded from a running stack. It needs no API
and opens on any device. Changes are refused; a banner at the bottom right says
"Read-only snapshot" and the time it was recorded.

To make a new snapshot from a running stack (API on :8300, web on :5180):

```bash
cd apps/web
node scripts/capture-snapshot.mjs     # records every page, tab and task, writes src/snapshot/data.b64
npm run build:snapshot                # → dist-snapshot/agent-one-finance-snapshot.html (one self-contained file)
```

**`agent-one-finance-snapshot.html` is one file with everything inside it.** Double-click it, or send it
to your team by email or Teams, and it opens in any browser: no server, no install, no login.
It also works on a phone. The current copy (three agents with their tasks, recorded 2026-10-19) is in
[`../demo/agent-one-finance-snapshot.html`](../demo/agent-one-finance-snapshot.html).

The capture records everything the console offers to open: every task it lists or names
(follow-ups and child tasks too), each run history step, eval runs, any two versions to
compare, the filters on the Tasks tab and the audit log, each configuration's check result
(shown on the Configure tab until you edit it), and the files behind the download buttons. So
nothing a viewer can click says it was not recorded. What stays live-only is anything that
changes data or asks the model (approving, sending, asking about a task): the snapshot says it
is read-only. Opening it needs a current browser (Chrome, Edge, Firefox, or Safari 16.4 or
later).

The build also leaves `snapshot.html` + `assets/` in `dist-snapshot/`, for hosting on a
static web server. The recorded responses are in `src/snapshot/data.b64` (gzipped JSON, so
the file stays small enough to email); recapture and rebuild to refresh them. The recorded data comes from the dev stack only, so never capture
a snapshot from an environment with real data.

Options for the capture script (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `AOF_WEB` | `http://localhost:5180` | the running web app |
| `SNAPSHOT_USER` | `frank` | who the screens are recorded as |
| `SNAPSHOT_TASKS` | — | extra task ids to include, comma-separated; every task the console lists is already in |
| `SNAPSHOT_AGENTS` | all | the agents to include, comma-separated ids, e.g. `recon.investigation,fin.accruals`; their tasks only, without the platform pages, with the walkthrough of the demo's example tasks (`src/snapshot/walkthrough.ts`) beside them |
| `SNAPSHOT_SCOPE` | `all` | `config`: the agents' configuration only, no tasks, inbox or operations |
| `PLAYWRIGHT` | `playwright` | module path, if Playwright is installed globally |
| `CHROMIUM` | — | a Chromium executable, if Playwright's own is not installed |

## 2. Live on your Mac

You need Docker Desktop, Python 3.11+ and Node 20+.

```bash
git clone https://github.com/praveen2025work/fobotower.git && cd fobotower
docker compose up -d postgres
cd apps/backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn agent_one_finance.web.main:app --port 8300          # leave running

# a second terminal
cd apps/web && npm install && npm run dev                  # http://localhost:5180
```

## 3. Live on your phone (same Wi-Fi as the Mac)

1. Start the web app so other devices can reach it:

   ```bash
   cd apps/web && npx vite --host
   ```

   The API stays on the Mac. The web app forwards `/api` calls to it.

2. On the phone, open `http://<your-mac-ip>:5180`. To find the IP, run
   `ipconfig getifaddr en0` on the Mac.

3. If the phone cannot connect, allow incoming connections for `node` under *System
   Settings → Network → Firewall*.

On a phone the menu sits behind the ☰ button. On a desktop the sidebar starts collapsed
to icons; use the arrow at its foot to expand it, and the choice is remembered.

> This is the dev setup: anyone on the same network can open it, and identities are the
> dev users. Do not use it with real data. In the office, Agent One Finance runs behind SSO.
