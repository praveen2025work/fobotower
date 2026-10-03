#!/usr/bin/env bash
# Start PostgreSQL 16 (with pgvector) on port 5433 and wait until it accepts
# connections. Matches the repo default DSN:
#   postgresql+asyncpg://fobo:fobo@localhost:5433/fobo
# Idempotent: safe to run repeatedly, tolerates an already-running server and a
# stale pidfile left behind by a snapshot / unclean shutdown.
set -euo pipefail

PGVER=16
PGCLUSTER=main
PGPORT=5433

# The base image already ships the "16 main" cluster; recreate it only if a
# fresh base ever lacks one.
if ! pg_lsclusters -h 2>/dev/null | awk '{print $1"/"$2}' | grep -qx "${PGVER}/${PGCLUSTER}"; then
  sudo pg_createcluster "${PGVER}" "${PGCLUSTER}"
fi

# Pin the listen port so the app's default DSN resolves without any override.
sudo pg_conftool "${PGVER}" "${PGCLUSTER}" set port "${PGPORT}"

# Drop a stale pidfile if the recorded process is no longer alive.
PIDFILE="/var/lib/postgresql/${PGVER}/${PGCLUSTER}/postmaster.pid"
if sudo test -f "${PIDFILE}"; then
  PGPID="$(sudo head -n1 "${PIDFILE}" 2>/dev/null || true)"
  if [ -n "${PGPID}" ] && ! sudo kill -0 "${PGPID}" 2>/dev/null; then
    sudo rm -f "${PIDFILE}"
  fi
fi

sudo pg_ctlcluster "${PGVER}" "${PGCLUSTER}" start || true

echo "==> Waiting for PostgreSQL on port ${PGPORT}"
for _ in $(seq 1 30); do
  if pg_isready -h localhost -p "${PGPORT}" >/dev/null 2>&1; then
    echo "PostgreSQL is ready on port ${PGPORT}"
    exit 0
  fi
  sleep 1
done

echo "PostgreSQL did not become ready on port ${PGPORT}" >&2
sudo tail -n 40 "/var/log/postgresql/postgresql-${PGVER}-${PGCLUSTER}.log" 2>/dev/null || true
exit 1
