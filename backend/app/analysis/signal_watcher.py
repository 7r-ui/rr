"""Periodically scans tracked symbols for new confluence signals and persists
them to Postgres, deduping against the last persisted signal per
(venue, symbol, timeframe) so an unchanged signal isn't re-inserted on every
scan tick.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.confluence import generate_signal
from app.core.db import SessionLocal
from app.ingestion.store import store
from app.models.db_models import SignalRecord
from app.models.schemas import TradeSignal, Venue

logger = logging.getLogger(__name__)

MIN_CANDLES_FOR_SIGNAL = 30


def _fingerprint(direction: str, ts: datetime, entry: float) -> tuple[str, datetime, float]:
    return (direction, ts, round(entry, 8))


async def _last_fingerprint(
    session: AsyncSession, venue: str, symbol: str, timeframe: str
) -> tuple[str, datetime, float] | None:
    stmt = (
        select(SignalRecord)
        .where(
            SignalRecord.venue == venue,
            SignalRecord.symbol == symbol,
            SignalRecord.timeframe == timeframe,
        )
        .order_by(SignalRecord.id.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return _fingerprint(row.direction, row.ts, row.entry)


async def _persist_signal(session: AsyncSession, signal: TradeSignal) -> None:
    session.add(
        SignalRecord(
            venue=signal.venue.value,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            direction=signal.direction.value,
            ts=signal.ts,
            confluence_score=signal.confluence_score,
            confluences=[f.model_dump() for f in signal.confluences],
            entry=signal.risk.entry,
            stop_loss=signal.risk.stop_loss,
            take_profits=signal.risk.take_profits,
            risk_reward=signal.risk.risk_reward,
            atr=signal.risk.atr,
            note=signal.note,
            created_at=datetime.now(tz=timezone.utc),
        )
    )
    await session.commit()


async def watch_signals(*, scan_interval: float, min_risk_reward: float) -> None:
    while True:
        await asyncio.sleep(scan_interval)
        for venue, symbol, timeframe in store.symbols():
            candles = store.get(venue, symbol, timeframe)
            if len(candles) < MIN_CANDLES_FOR_SIGNAL:
                continue

            signal = generate_signal(
                candles,
                symbol=symbol,
                venue=Venue(venue),
                timeframe=timeframe,
                min_risk_reward=min_risk_reward,
            )
            if signal is None:
                continue

            async with SessionLocal() as session:
                last = await _last_fingerprint(session, venue, symbol, timeframe)
                current = _fingerprint(
                    signal.direction.value, signal.ts, signal.risk.entry
                )
                if last == current:
                    continue
                await _persist_signal(session, signal)
                logger.info(
                    "Persisted new %s signal for %s:%s:%s",
                    signal.direction.value, venue, symbol, timeframe,
                )
