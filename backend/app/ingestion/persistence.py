"""Durably persists confirmed candles from Redis into Postgres.

Only confirmed bars are written — an in-progress candle updates on every
tick and would otherwise write-amplify the DB for no benefit, since the
in-memory `CandleStore` already serves the live/unconfirmed view. Batches
by count OR time (whichever comes first) via a queue + separate flusher
task, so a quiet period doesn't strand a partial batch unflushed.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionLocal
from app.core.redis_bus import bus
from app.models.db_models import CandleRecord
from app.models.schemas import Candle

logger = logging.getLogger(__name__)


async def _flush(batch: list[Candle]) -> None:
    if not batch:
        return
    rows = [
        {
            "venue": c.venue.value,
            "symbol": c.symbol,
            "timeframe": c.timeframe,
            "open_time": c.open_time,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
            "confirmed": c.confirmed,
        }
        for c in batch
    ]
    async with SessionLocal() as session:
        stmt = pg_insert(CandleRecord).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_candle_key",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "confirmed": stmt.excluded.confirmed,
            },
        )
        await session.execute(stmt)
        await session.commit()
    logger.debug("Flushed %d candle(s) to Postgres", len(batch))


async def _ingest(channels: list[str], queue: asyncio.Queue[Candle]) -> None:
    async for payload in bus.subscribe(*channels):
        try:
            candle = Candle(**payload)
        except (TypeError, ValueError) as exc:
            logger.debug("Skipping malformed candle payload: %s", exc)
            continue
        if candle.confirmed:
            await queue.put(candle)


async def _flusher(queue: asyncio.Queue[Candle], *, batch_size: int, flush_interval: float) -> None:
    """Flushes whenever the batch hits `batch_size`, or after `flush_interval`
    seconds pass with nothing new arriving (so a quiet period still flushes
    whatever partial batch is pending)."""
    batch: list[Candle] = []
    while True:
        try:
            candle = await asyncio.wait_for(queue.get(), timeout=flush_interval)
            batch.append(candle)
            if len(batch) < batch_size:
                continue
        except TimeoutError:
            pass
        await _flush(batch)
        batch = []


async def persist_candles(channels: list[str], *, batch_size: int, flush_interval: float) -> None:
    queue: asyncio.Queue[Candle] = asyncio.Queue()
    await asyncio.gather(
        _ingest(channels, queue),
        _flusher(queue, batch_size=batch_size, flush_interval=flush_interval),
    )
