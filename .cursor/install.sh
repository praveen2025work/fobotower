#!/usr/bin/env bash
# FOBO Investigation Console — repository bootstrap.
# Idempotent: prepares the Python venv + deps, the Node console deps, ensures
# the fobo role/database exist, and applies migrations. Safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

echo "==> Ensuring uv is available"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "==> Ensuring PostgreSQL is running (migrations need it)"
bash "${REPO_ROOT}/.cursor/db.sh"

echo "==> Ensuring the fobo role and database exist"
# The app connects as a superuser (matching docker-compose's POSTGRES_USER),
# which is required to CREATE EXTENSION vector during migration.
if ! sudo -u postgres psql -p 5433 -tAc "SELECT 1 FROM pg_roles WHERE rolname='fobo'" | grep -q 1; then
  sudo -u postgres psql -p 5433 -c "CREATE ROLE fobo LOGIN SUPERUSER PASSWORD 'fobo';"
fi
if ! sudo -u postgres psql -p 5433 -tAc "SELECT 1 FROM pg_database WHERE datname='fobo'" | grep -q 1; then
  sudo -u postgres createdb -p 5433 -O fobo fobo
fi

echo "==> Installing API dependencies (Python 3.12 venv)"
cd "${REPO_ROOT}/apps/api"
if [ ! -x ".venv/bin/python" ]; then
  uv venv --python 3.12
fi
uv pip install -e ".[dev]"

echo "==> Applying database migrations"
.venv/bin/alembic upgrade head

echo "==> Installing console dependencies"
cd "${REPO_ROOT}/apps/console"
npm ci

echo "==> Install complete"
