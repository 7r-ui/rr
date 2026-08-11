"""Starts and supervises every ingestion source as background asyncio tasks.

Each source runs independently with its own reconnect/backoff loop, so a
Binance outage never blocks Bybit/OANDA/Polygon feeds. Tasks that raise are
logged and NOT silently swallowed forever - `run_forever` restarts a task
if it exits unexpectedly.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.redis_bus import candle_channel
from app.ingestion.binance_ws import stream_binance_klines
from app.ingestion.bybit_ws import stream_bybit_klines
from app.ingestion.oanda_client import stream_oanda_prices
from app.ingestion.polygon_client import stream_polygon_quotes
from app.ingestion.store import sync_candle_store

logger = logging.getLogger(__name__)

DEFAULT_TIMEFRAME = "1m"


async def _supervise(name: str, coro_factory) -> None:
    while True:
        try:
            await coro_factory()
            logger.warning("Ingestion task '%s' exited cleanly, restarting in 5s", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ingestion task '%s' crashed, restarting in 5s", name)
        await asyncio.sleep(5)


def build_ingestion_tasks() -> list[asyncio.Task]:
    settings = get_settings()
    crypto_symbols = settings.default_symbols_crypto
    fx_symbols = settings.default_symbols_fx

    candle_channels = [
        candle_channel("binance", s, DEFAULT_TIMEFRAME) for s in crypto_symbols
    ] + [candle_channel("bybit", s, DEFAULT_TIMEFRAME) for s in crypto_symbols]

    tasks = [
        asyncio.create_task(
            _supervise(
                "binance",
                lambda: stream_binance_klines(crypto_symbols, DEFAULT_TIMEFRAME),
            )
        ),
        asyncio.create_task(
            _supervise(
                "bybit", lambda: stream_bybit_klines(crypto_symbols, DEFAULT_TIMEFRAME)
            )
        ),
        asyncio.create_task(
            _supervise("oanda", lambda: stream_oanda_prices(fx_symbols))
        ),
        asyncio.create_task(
            _supervise(
                "polygon",
                lambda: stream_polygon_quotes(
                    [s.replace("_", "") for s in fx_symbols]
                ),
            )
        ),
        asyncio.create_task(
            _supervise("candle-store-sync", lambda: sync_candle_store(candle_channels))
        ),
    ]
    return tasks
