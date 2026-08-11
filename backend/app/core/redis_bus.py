"""Thin wrapper around Redis Pub/Sub used to decouple ingestion from consumers
(API WebSocket fan-out, the signal engine, etc.) so a burst on one exchange
feed can't block another."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings


class RedisBus:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or get_settings().redis_url
        self._client: redis.Redis | None = None

    async def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        client = await self.client()
        await client.publish(channel, json.dumps(payload, default=str))

    async def subscribe(self, *channels: str) -> AsyncIterator[dict[str, Any]]:
        client = await self.client()
        pubsub = client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    yield json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


bus = RedisBus()


def candle_channel(venue: str, symbol: str, timeframe: str) -> str:
    return f"candles:{venue}:{symbol}:{timeframe}"


def tick_channel(venue: str, symbol: str) -> str:
    return f"ticks:{venue}:{symbol}"


def signal_channel(symbol: str) -> str:
    return f"signals:{symbol}"
