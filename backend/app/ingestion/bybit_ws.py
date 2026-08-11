"""Live kline ingestion from Bybit's v5 public WebSocket (linear perpetuals).

Docs: https://bybit-exchange.github.io/docs/v5/websocket/public/kline
Bybit intervals are numeric-minute strings ("1","5","15","60","240","D").
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

BYBIT_INTERVAL_MAP = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}


def _parse_kline_message(msg: dict, symbol: str, timeframe: str) -> Candle | None:
    data = msg.get("data")
    if not data:
        return None
    k = data[0] if isinstance(data, list) else data
    return Candle(
        symbol=symbol.lower(),
        venue=Venue.BYBIT,
        timeframe=timeframe,
        open_time=datetime.fromtimestamp(int(k["start"]) / 1000, tz=timezone.utc),
        open=float(k["open"]),
        high=float(k["high"]),
        low=float(k["low"]),
        close=float(k["close"]),
        volume=float(k["volume"]),
        confirmed=bool(k["confirm"]),
    )


async def stream_bybit_klines(
    symbols: list[str], interval: str = "1m", *, max_backoff: float = 60.0
) -> None:
    settings = get_settings()
    bybit_interval = BYBIT_INTERVAL_MAP.get(interval, "1")
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(
                settings.bybit_ws_url, ping_interval=20, ping_timeout=20
            ) as ws:
                topics = [f"kline.{bybit_interval}.{s.upper()}" for s in symbols]
                await ws.send(json.dumps({"op": "subscribe", "args": topics}))
                logger.info("Connected to Bybit stream, subscribed: %s", topics)
                backoff = 1.0
                async for raw in ws:
                    msg = json.loads(raw)
                    topic = msg.get("topic", "")
                    if not topic.startswith("kline."):
                        continue
                    symbol = topic.split(".")[-1]
                    candle = _parse_kline_message(msg, symbol, interval)
                    if candle is None:
                        continue
                    await bus.publish(
                        candle_channel("bybit", candle.symbol, candle.timeframe),
                        candle.model_dump(),
                    )
        except (websockets.exceptions.WebSocketException, OSError) as exc:
            logger.warning("Bybit stream error (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
