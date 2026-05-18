"""Async SQLModel engine + session helpers."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL, echo=False, future=True
)

_AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Dev convenience — create tables. Replace with Alembic later."""
    # Import models so SQLModel.metadata sees them.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # Best-effort additive migrations. create_all() does NOT alter
        # existing tables, so columns added after the table was first
        # created (like cal_booking_uid in Phase 7) need an explicit
        # ALTER. Postgres-only — IF NOT EXISTS makes it safe to re-run.
        for table in ("call_logs", "outbound_calls"):
            await conn.exec_driver_sql(
                f"ALTER TABLE {table} "
                "ADD COLUMN IF NOT EXISTS cal_booking_uid TEXT NULL"
            )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Use inside services that aren't request-scoped (onboarding, WS handler)."""
    async with _AsyncSessionLocal() as session:
        yield session
