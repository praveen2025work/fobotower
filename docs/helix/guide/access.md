# Opening Helix on a Mac or phone

## 1. Read-only snapshot (no setup)

A snapshot is the real web app over data recorded from a running stack. It needs no API
and opens on any device. Changes are refused; a banner at the bottom right says
"Read-only snapshot" and the time it was recorded.

To make a new snapshot from a running stack (API on :8300, web on :5180):

```bash
cd apps/web
node scripts/capture-snapshot.mjs     # walks the main screens, writes src/snapshot/data.json
npm run build:snapshot                # → dist-snapshot/ (snapshot.html + assets, relative paths)
```

Then host `dist-snapshot/` anywhere static, or open it with `npx vite preview --outDir
dist-snapshot`. The current snapshot (dev data, recorded 2026-10-04) is committed:
the recorded responses in `src/snapshot/data.json` and the built copy in
`dist-snapshot/` (open `index.html`). Recapture and rebuild to refresh both. The
recorded data comes from the dev stack only, so never capture a snapshot from an
environment with real data.

Options for the capture script (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `HELIX_WEB` | `http://localhost:5180` | the running web app |
| `SNAPSHOT_USER` | `frank` | who the screens are recorded as |
| `PLAYWRIGHT` | `playwright` | module path, if Playwright is installed globally |
| `CHROMIUM` | — | a Chromium executable, if Playwright's own is not installed |

## 2. Live on your Mac

You need Docker Desktop, Python 3.11+ and Node 20+.

```bash
git clone https://github.com/praveen2025work/fobotower.git && cd fobotower
docker compose up -d postgres
cd apps/backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn helix.web.main:app --port 8300          # leave running

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
> dev users. Do not use it with real data. In the office, Helix runs behind SSO.
