import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from agent_one_finance import models as aof_models  # noqa: F401  register aof_* tables
from agent_one_finance.config import settings as aof_settings
from agent_one_finance.db import AofBase
target_metadata = [AofBase.metadata]
DATABASE_URL = aof_settings().database_url
# The first migrations (aa1b933c1055 … e5a7c3d9f1b2) created the original FOBO app's tables.
# They stay in the history so existing databases upgrade cleanly; those tables are not
# in this metadata, so autogenerate must not drop them (see include_object below).
LEGACY_FOBO_TABLES = {"session_message", "source_call", "controller_decision", "pattern_group", "evidence_item",
                      "analysis_version", "agent_session", "investigation_session", "workflow_version",
                      "break_embedding", "break_event", "edge", "node", "run", "reconciliation"}

# Migrate the same database the app uses (AOF_DATABASE_URL, else FOBO_DATABASE_URL,
# else the local dev default). `%` is doubled because the ini parser interpolates it.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

# LangGraph's Postgres checkpointer creates and owns these. They are not in
# our metadata, so autogenerate would emit DROP statements for them.
CHECKPOINTER_TABLES = {
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
}


def include_object(object, name, type_, reflected, compare_to):
    keep_out = CHECKPOINTER_TABLES | LEGACY_FOBO_TABLES
    if type_ == "table" and name in keep_out:
        return False
    if type_ == "index" and getattr(object, "table", None) is not None:
        return object.table.name not in keep_out
    return True



# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
