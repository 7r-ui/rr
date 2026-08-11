"""In-memory rolling candle store, kept in sync from the Redis candle channels.

Analysis (SMC/Elliott/risk) needs windowed OHLCV history, not single ticks,
so this maintains a bounded deque per (venue, symbol, timeframe) fed by a
background Redis subscriber.
"""
from __future__ import annotations

import logging
from collections import deque

from app.core.redis_bus import bus
from app.models.schemas import Candle

logger = logging.getLogger(__name__)

MAX_CANDLES = 1000


class CandleStore:
    def __init__(self) -> None:
        self._series: dict[tuple[str, str, str], deque[Candle]] = {}

    def key(self, venue: str, symbol: str, timeframe: str) -> tuple[str, str, str]:
        return (venue, symbol.lower(), timeframe)

    def upsert(self, candle: Candle) -> None:
        key = self.key(candle.venue.value, candle.symbol, candle.timeframe)
        series = self._series.setdefault(key, deque(maxlen=MAX_CANDLES))
        if series and series[-1].open_time == candle.open_time:
            series[-1] = candle
        else:
            series.append(candle)

    def get(self, venue: str, symbol: str, timeframe: str) -> list[Candle]:
        return list(self._series.get(self.key(venue, symbol, timeframe), []))

    def symbols(self) -> list[tuple[str, str, str]]:
        return list(self._series.keys())


store = CandleStore()


async def sync_candle_store(channels: list[str]) -> None:
    """Subscribe to explicit candle channels and keep the in-memory store updated."""
    async for payload in bus.subscribe(*channels):
        try:
            candle = Candle(**payload)
        except (TypeError, ValueError) as exc:
            logger.debug("Skipping malformed candle payload: %s", exc)
            continue
        store.upsert(candle)
