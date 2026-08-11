"""Polygon.io WebSocket client for forex/metals quotes (institutional-grade feed).

Docs: https://polygon.io/docs/websockets/forex/quotes
Requires POLYGON_API_KEY; stays idle without one so the rest of the
platform still runs.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets

from app.core.config import get_settings
from app.core.redis_bus import bus, tick_channel
from app.models.schemas import Tick, Venue

logger = logging.getLogger(__name__)

POLYGON_FOREX_WS = "wss://socket.polygon.io/forex"


async def stream_polygon_quotes(pairs: list[str], *, max_backoff: float = 60.0) -> None:
    """`pairs` like ["C:EURUSD", "C:XAUUSD"] (Polygon's forex/metals ticker format)."""
    settings = get_settings()
    if not settings.polygon_api_key:
        logger.info("Polygon.io API key not configured; Polygon ingestion disabled.")
        await asyncio.Event().wait()  # park forever rather than looping the supervisor
        return

    backoff = 1.0
    while True:
        try:
            async with websockets.connect(POLYGON_FOREX_WS, ping_interval=20) as ws:
                await ws.send(json.dumps({"action": "auth", "params": settings.polygon_api_key}))
                sub_params = ",".join(f"C.{p}" for p in pairs)
                await ws.send(json.dumps({"action": "subscribe", "params": sub_params}))
                logger.info("Connected to Polygon.io forex stream: %s", pairs)
                backoff = 1.0
                async for raw in ws:
                    events = json.loads(raw)
                    if not isinstance(events, list):
                        continue
                    for event in events:
                        if event.get("ev") != "C":
                            continue
                        bid, ask = event.get("b"), event.get("a")
                        if bid is None or ask is None:
                            continue
                        tick = Tick(
                            symbol=event.get("p", "unknown"),
                            venue=Venue.POLYGON,
                            price=(float(bid) + float(ask)) / 2,
                            ts=datetime.now(tz=timezone.utc),
                        )
                        await bus.publish(
                            tick_channel("polygon", tick.symbol), tick.model_dump()
                        )
        except (websockets.exceptions.WebSocketException, OSError) as exc:
            logger.warning("Polygon.io stream error (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
