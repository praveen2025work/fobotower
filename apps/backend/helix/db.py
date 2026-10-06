"""Agent One Finance's own metadata and session factory.

Separate from fobo's: Agent One Finance tables are prefixed `helix_` and live in the same
database, so both run side by side until FOBO moves onto the platform.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from helix.config import settings


class HelixBase(DeclarativeBase):
    pass


engine = create_async_engine(settings().database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session():
    async with SessionFactory() as session:
        yield session


def checkpoint_dsn() -> str:
    """LangGraph's checkpointer uses psycopg, not asyncpg."""
    return settings().database_url.replace("+asyncpg", "")
