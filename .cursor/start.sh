#!/usr/bin/env bash
# Per-boot startup for the FOBO Investigation Console.
# Ensures PostgreSQL is up (hard requirement) and launches the API and console
# dev servers in the background (best-effort). Idempotent: a server that is
# already listening is left alone.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

# --- PostgreSQL (required) ---------------------------------------------------
bash "${REPO_ROOT}/.cursor/db.sh"

# --- Dev servers (best-effort) ----------------------------------------------
port_is_up() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- 3<&- ; }

start_bg() {
  local name="$1" port="$2" logfile="$3" workdir="$4"; shift 4
  if port_is_up "${port}"; then
    echo "==> ${name} already listening on ${port}"
    return 0
  fi
  echo "==> Starting ${name} on port ${port} (logs: ${logfile})"
  ( cd "${workdir}" && nohup "$@" >"${logfile}" 2>&1 & )
}

start_bg "API" 8100 /tmp/fobo-api.log "${REPO_ROOT}/apps/api" \
  "${REPO_ROOT}/apps/api/.venv/bin/uvicorn" api.main:app --host 0.0.0.0 --port 8100

start_bg "console" 3100 /tmp/fobo-console.log "${REPO_ROOT}/apps/console" \
  npm run dev

echo "==> Startup complete (Postgres:5433, API:8100, console:3100)"
