#!/usr/bin/env bash
# Per-boot startup: ensure PostgreSQL 16 (pgvector) is up on port 5433.
# The API and console dev servers run as `terminals` (see environment.json),
# so this only reconciles the database daemon. Idempotent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${REPO_ROOT}/.cursor/db.sh"
