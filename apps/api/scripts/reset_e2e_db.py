"""Create an empty fobo_e2e database with the current schema.

    FOBO_DATABASE_URL=postgresql+asyncpg://fobo:fobo@localhost:5433/fobo_e2e \
        .venv/bin/python scripts/reset_e2e_db.py

Refuses any other database name: it drops the database it is pointed at.
"""

import asyncio
import os
import sys

import asyncpg
from sqlalchemy import text

URL = os.environ.get("FOBO_DATABASE_URL", "")
NAME = "fobo_e2e"


async def main() -> None:
    raw = URL.replace("+asyncpg", "")
    admin = raw.rsplit("/", 1)[0] + "/postgres"
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{NAME}"')
    finally:
        await conn.close()

    from app.db import models_graph, models_ops, models_session, models_workflow  # noqa: F401
    from app.db.base import Base, engine

    async with engine.begin() as c:
        await c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await c.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    if not URL.endswith(f"/{NAME}"):
        sys.exit(f"refusing: FOBO_DATABASE_URL must point at the {NAME} database")
    asyncio.run(main())
