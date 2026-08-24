"""Receives TradingView `alert()` webhooks carrying OHLCV data straight from
a chart, so a symbol Claude is watching doesn't need a dedicated exchange
feed wired up in app/ingestion — pointing a Pine Script alert here is enough.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import get_settings
from app.core.redis_bus import bus, candle_channel
from app.ingestion.store import store
from app.models.schemas import Candle, TradingViewAlertPayload, Venue

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _check_secret(secret: str | None, x_webhook_secret: str | None) -> None:
    settings = get_settings()
    if not settings.tradingview_webhook_secret:
        return
    provided = x_webhook_secret or secret
    if provided != settings.tradingview_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret.")


@router.post("/tradingview")
async def tradingview_alert(
    payload: TradingViewAlertPayload,
    secret: str | None = Query(default=None),
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, str]:
    _check_secret(secret, x_webhook_secret)

    candle = Candle(
        symbol=payload.symbol.lower(),
        venue=Venue.TRADINGVIEW,
        timeframe=payload.timeframe,
        open_time=payload.time or datetime.now(tz=timezone.utc),
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
        confirmed=True,
    )
    store.upsert(candle)
    await bus.publish(
        candle_channel(Venue.TRADINGVIEW.value, candle.symbol, candle.timeframe),
        candle.model_dump(),
    )
    return {"status": "accepted", "symbol": candle.symbol, "timeframe": candle.timeframe}
