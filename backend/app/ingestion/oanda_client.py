"""OANDA v20 REST/streaming client for forex + metals pricing.

OANDA's pricing stream is a chunked-HTTP long-lived connection (not a
WebSocket), documented at:
https://developer.oanda.com/rest-live-v20/pricing-ep/
Requires OANDA_API_KEY and OANDA_ACCOUNT_ID; without them this stays idle
rather than raising, so the rest of the platform still runs on crypto data.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings
from app.core.redis_bus import bus, tick_channel
from app.models.schemas import Tick, Venue

logger = logging.getLogger(__name__)


def _stream_host(base_url: str) -> str:
    return base_url.replace("api-fx", "stream-fx")


async def stream_oanda_prices(instruments: list[str], *, max_backoff: float = 60.0) -> None:
    settings = get_settings()
    if not settings.oanda_api_key or not settings.oanda_account_id:
        logger.info("OANDA credentials not configured; OANDA ingestion disabled.")
        await asyncio.Event().wait()  # park forever rather than looping the supervisor
        return

    url = (
        f"{_stream_host(settings.oanda_base_url)}/v3/accounts/"
        f"{settings.oanda_account_id}/pricing/stream"
    )
    headers = {"Authorization": f"Bearer {settings.oanda_api_key}"}
    params = {"instruments": ",".join(instruments)}
    backoff = 1.0

    while True:
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", url, headers=headers, params=params) as resp:
                    resp.raise_for_status()
                    backoff = 1.0
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        msg = json.loads(line)
                        if msg.get("type") != "PRICE":
                            continue
                        bids = msg.get("bids", [])
                        asks = msg.get("asks", [])
                        if not bids or not asks:
                            continue
                        mid = (float(bids[0]["price"]) + float(asks[0]["price"])) / 2
                        tick = Tick(
                            symbol=msg["instrument"],
                            venue=Venue.OANDA,
                            price=mid,
                            ts=datetime.now(tz=timezone.utc),
                        )
                        await bus.publish(
                            tick_channel("oanda", tick.symbol), tick.model_dump()
                        )
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("OANDA stream error (%s), reconnecting in %.1fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
