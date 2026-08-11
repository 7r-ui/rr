from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.redis_bus import bus, candle_channel
from app.ingestion.store import store
from app.models.schemas import Candle

router = APIRouter(prefix="/market", tags=["market-data"])


@router.get("/candles", response_model=list[Candle])
async def get_candles(venue: str, symbol: str, timeframe: str = "1m", limit: int = 200) -> list[Candle]:
    candles = store.get(venue, symbol, timeframe)
    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No cached candles yet for {venue}:{symbol}:{timeframe} — ingestion may still be warming up.",
        )
    return candles[-limit:]


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
