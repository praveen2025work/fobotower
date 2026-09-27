import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "FOBO_DATABASE_URL", "postgresql+asyncpg://fobo:fobo@localhost:5433/fobo"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_session():
    async with SessionFactory() as session:
        yield session
