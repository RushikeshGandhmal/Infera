"""Database engine, session factory, and table creation.

Uses SQLAlchemy 2.0 with the async asyncpg driver so DB calls don't block the
event loop (important when the gateway is also streaming responses).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Parent class for all ORM models."""


settings = get_settings()

# One engine per process; pool_pre_ping avoids using a dead connection.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_models() -> None:
    """Create tables if they don't exist (called on startup)."""
    from . import models  # noqa: F401 - import so models register on Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session and closes it after the request."""
    async with SessionLocal() as session:
        yield session
