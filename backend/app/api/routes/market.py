from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.redis_bus import bus, candle_channel
from app.ingestion.store import store
from app.models.db_models import CandleRecord
from app.models.schemas import Candle, Venue

router = APIRouter(prefix="/market", tags=["market-data"])

MAX_HISTORY_LIMIT = 5000


@router.get("/candles", response_model=list[Candle])
async def get_candles(venue: str, symbol: str, timeframe: str = "1m", limit: int = 200) -> list[Candle]:
    """Live/recent candles from the in-memory ring buffer (bounded window,
    includes the still-forming bar). For older history use /candles/history."""
    candles = store.get(venue, symbol, timeframe)
    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No cached candles yet for {venue}:{symbol}:{timeframe} — ingestion may still be warming up.",
        )
    return candles[-limit:]


@router.get("/candles/history", response_model=list[Candle])
async def get_candle_history(
    venue: str,
    symbol: str,
    timeframe: str = "1m",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
    session: AsyncSession = Depends(get_session),
) -> list[Candle]:
    """Durable, DB-backed history — only confirmed bars, unbounded by the
    in-memory ring buffer's window. Use this for backtesting/charting ranges
    older than what /candles currently holds."""
    limit = min(limit, MAX_HISTORY_LIMIT)
    stmt = (
        select(CandleRecord)
        .where(
            CandleRecord.venue == venue,
            CandleRecord.symbol == symbol.lower(),
            CandleRecord.timeframe == timeframe,
        )
        .order_by(CandleRecord.open_time.desc())
        .limit(limit)
    )
    if start is not None:
        stmt = stmt.where(CandleRecord.open_time >= start)
    if end is not None:
        stmt = stmt.where(CandleRecord.open_time <= end)

    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted candles for {venue}:{symbol}:{timeframe} in that range yet.",
        )
    candles = [
        Candle(
            symbol=r.symbol,
            venue=Venue(r.venue),
            timeframe=r.timeframe,
            open_time=r.open_time,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
            confirmed=r.confirmed,
        )
        for r in rows
    ]
    return list(reversed(candles))


@router.get("/symbols")
async def list_symbols() -> list[dict[str, str]]:
    return [
        {"venue": v, "symbol": s, "timeframe": tf} for v, s, tf in store.symbols()
    ]


@router.websocket("/ws/{venue}/{symbol}/{timeframe}")
async def market_ws(websocket: WebSocket, venue: str, symbol: str, timeframe: str) -> None:
    """Fans out live candle updates for one venue/symbol/timeframe over WebSocket,
    bridging the internal Redis Pub/Sub channel to the browser client."""
    await websocket.accept()
    channel = candle_channel(venue, symbol, timeframe)
    try:
        async for payload in bus.subscribe(channel):
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
