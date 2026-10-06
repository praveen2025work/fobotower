# Renamed: Helix is now Agent One Finance

**Date:** 2026-10-06. The platform's code, configuration and database now use the Agent One
Finance names. FOBO keeps its own names (`fobo` package, `FOBO_*` settings, the FOBO console).
An office deployment that was set up under the old names changes the items below in one release.

## What to change

| Area | Was | Now |
|---|---|---|
| Python package | `helix` (`helix.web.main:app`) | `agent_one_finance` (`agent_one_finance.web.main:app`) |
| Folders | `apps/backend/helix`, `config/helix`, `docs/helix`, `tests/helix` | `apps/backend/agent_one_finance`, `config/agent-one-finance`, `docs/agent-one-finance`, `tests/agent_one_finance` |
| Settings (environment) | `HELIX_*`, e.g. `HELIX_LLM_ADAPTER`, `HELIX_ENTITLEMENT_URL`, `HELIX_DATABASE_URL` | `AOF_*`, e.g. `AOF_LLM_ADAPTER`, `AOF_ENTITLEMENT_URL`, `AOF_DATABASE_URL` (same suffix) |
| HTTP headers | `X-Helix-User`, `X-Helix-Event-Secret`, `X-Helix-Proxy-Secret`, `X-Helix-Webhook-Secret` | `X-AOF-User`, `X-AOF-Event-Secret`, `X-AOF-Proxy-Secret`, `X-AOF-Webhook-Secret` |
| Roles (entitlement system) | `HELIX_*_OWNER`, `HELIX_PLATFORM_ADMIN` | `AOF_*_OWNER`, `AOF_PLATFORM_ADMIN` |
| Entitlement lookup | `?app=helix` | `?app=aof` |
| Scheduler user | `helix-scheduler` | `aof-scheduler` |
| Database tables | `helix_*` (and their indexes, constraints, sequences) | `aof_*` |
| Workflow checkpoints | thread ids `helix:<case id>` | `aof:<case id>` |
| Model tools | MCP server `helix` (`mcp__helix__…`) | `aof` (`mcp__aof__…`) |
| Trace attributes | `helix.case_id`, `helix.allowed`, … | `aof.case_id`, `aof.allowed`, … |
| Browser storage | `helix.user`, `helix.theme` | `aof.user`, `aof.theme` (users pick their user and theme once more) |

## Order of the release

1. Rename the roles in the entitlement system (or add the `AOF_*` roles beside the old ones for
   the cut-over) and rename the environment settings; point any proxy or bot at the new headers.
2. Deploy the new build.
3. Run `alembic upgrade head`. Migration `e7f9a1b3c5d7` renames the tables, indexes,
   constraints and sequences, moves stored role names and the scheduler user to the new names,
   and re-keys the workflow checkpoints, so open cases carry on. `alembic downgrade -1` reverses it.
4. Run `python -m agent_one_finance.config_sync` if configuration files changed, and approve the
   drafts as a second owner.

Old migration files keep their original names and contents: they are the history the new
migration builds on.
