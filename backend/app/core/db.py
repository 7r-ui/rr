"""Async SQLAlchemy engine/session setup for the persistence layer.

The in-memory `CandleStore` (app/ingestion/store.py) stays the hot path for
live chart/analysis reads — this is the durable layer behind it: confirmed
candles and generated signals survive a backend restart and are queryable
beyond the in-memory ring buffer's window.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine():
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


engine = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
