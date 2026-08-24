from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.alerts.dispatcher import dispatch_signal_alert
from app.analysis.confluence import generate_signal
from app.analysis.smc import MarketStructureResult, analyze_market_structure
from app.core.config import get_settings
from app.ingestion.store import store
from app.models.schemas import TradeSignal, Venue

router = APIRouter(tags=["signals"])


def _load_candles(venue: str, symbol: str, timeframe: str):
    candles = store.get(venue, symbol, timeframe)
    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"No cached candles yet for {venue}:{symbol}:{timeframe} — ingestion may still be warming up.",
        )
    return candles


@router.get("/structure", response_model=MarketStructureResult)
async def get_structure(venue: str, symbol: str, timeframe: str = "1m") -> MarketStructureResult:
    candles = _load_candles(venue, symbol, timeframe)
    return analyze_market_structure(candles)


@router.get("/signals", response_model=TradeSignal | None)
async def get_signal(
    venue: str,
    symbol: str,
    timeframe: str = "1m",
    account_balance: float | None = None,
    risk_pct: float | None = None,
) -> TradeSignal | None:
    candles = _load_candles(venue, symbol, timeframe)
    settings = get_settings()
    return generate_signal(
        candles,
        symbol=symbol,
        venue=Venue(venue),
        timeframe=timeframe,
        min_risk_reward=settings.min_risk_reward,
        account_balance=account_balance or settings.default_account_balance,
        risk_pct=risk_pct or settings.default_risk_pct,
    )


@router.post("/signals/notify")
async def notify_signal(
    venue: str,
    symbol: str,
    timeframe: str = "1m",
    account_balance: float | None = None,
    risk_pct: float | None = None,
) -> dict:
    """Generates a signal exactly like GET /signals, and — if one fires —
    pushes it to whichever of Telegram/Discord are configured. Side-effecting,
    so it's a POST rather than folded into the read-only GET /signals."""
    signal = await get_signal(
        venue, symbol, timeframe, account_balance=account_balance, risk_pct=risk_pct
    )
    if signal is None:
        return {"signal": None, "delivered": {}}
    delivered = await dispatch_signal_alert(signal)
    return {"signal": signal, "delivered": delivered}
