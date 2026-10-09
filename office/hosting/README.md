# Hosting templates for the AOF API (aos-backend)

Copied into aos-backend once, then owned there (the sync tool never touches them). How to use them:
[`docs/agent-one-finance/office/conversion-guide.md`](../../docs/agent-one-finance/office/conversion-guide.md),
section 8.

| File | In aos-backend |
|---|---|
| `Dockerfile.aof` | Replaces the contents of `Dockerfile.helix`: the AOF API image (port 8300) |
| `aof_alembic.ini` | `aof_alembic.ini`, next to `aof_migrations/` |
| `aof_forward.py` | A reference for the Agent One API's `/finance/api/*` route: checks the sign-on, then calls the AOF service |
