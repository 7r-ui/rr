"""Live kline ingestion from Binance's combined-stream WebSocket.

Docs: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-streams
Reconnects with exponential backoff since exchange WS endpoints drop
connections periodically (Binance forcibly closes after 24h).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from app.core.config import get_settings
from app.core.redis_bus import bus, candle_channel
from app.models.schemas import Candle, Venue

logger = logging.getLogger(__name__)

BINANCE_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]


def _stream_url(symbols: list[str], interval: str) -> str:
    settings = get_settings()
    streams = "/".join(f"{s.lower()}@kline_{interval}" for s in symbols)
    return f"{settings.binance_ws_url}?streams={streams}"


def _parse_kline_message(msg: dict) -> Candle | None:
    data = msg.get("data", {})
    k = data.get("k")
    if not k:
        return None
    return Candle(
        symbol=data["s"].lower(),
        venue=Venue.BINANCE,
        timeframe=k["i"],
        open_time=datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
        open=float(k["o"]),
        high=float(k["h"]),
        low=float(k["l"]),
        close=float(k["c"]),
        volume=float(k["v"]),
        confirmed=bool(k["x"]),
    )


async def stream_binance_klines(
    symbols: list[str], interval: str = "1m", *, max_backoff: float = 60.0
) -> None:
    backoff = 1.0
    url = _stream_url(symbols, interval)
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                logger.info("Connected to Binance stream: %s", url)
                backoff = 1.0
                async for raw in ws:
                    msg = json.loads(raw)
                    candle = _parse_kline_message(msg)
                    if candle is None:
                        continue
                    await bus.publish(
                        candle_channel("binance", candle.symbol, candle.timeframe),
                        candle.model_dump(),
                    )
        except (websockets.exceptions.WebSocketException, OSError) as exc:
            logger.warning("Binance stream error (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
