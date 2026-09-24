#!/bin/bash
# Prepares a Claude Code on the web container: API venv, console packages,
# and Postgres 16 + pgvector on :5433 (the container has no Docker, so this
# stands in for `docker compose up -d postgres`).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PG_CONF=/etc/postgresql/16/main/postgresql.conf

# Postgres 16 with pgvector, on the port docker-compose.yml publishes.
if [ ! -f /usr/share/postgresql/16/extension/vector.control ]; then
  apt-get install -y -q postgresql-16-pgvector >/dev/null 2>&1 \
    || { apt-get update -q >/dev/null && apt-get install -y -q postgresql-16-pgvector >/dev/null; }
fi
sed -i 's/^port = .*/port = 5433/' "$PG_CONF"
service postgresql start >/dev/null
for _ in $(seq 1 20); do pg_isready -q -p 5433 && break; sleep 1; done
su postgres -c "psql -p 5433 -tAc \"SELECT 1 FROM pg_roles WHERE rolname='fobo'\"" | grep -q 1 \
  || su postgres -c "psql -p 5433 -qc \"CREATE USER fobo WITH PASSWORD 'fobo' SUPERUSER\""
su postgres -c "psql -p 5433 -tAc \"SELECT 1 FROM pg_database WHERE datname='fobo'\"" | grep -q 1 \
  || su postgres -c "createdb -p 5433 -O fobo fobo"

# API
cd "$ROOT/apps/api"
[ -x .venv/bin/python ] || uv venv --python 3.12 -q
uv pip install -q -e ".[dev]"
.venv/bin/alembic upgrade head >/dev/null

# Console
cd "$ROOT/apps/console"
npm install --no-audit --no-fund --loglevel=error
