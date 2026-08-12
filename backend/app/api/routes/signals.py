from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.confluence import generate_signal
from app.analysis.smc import MarketStructureResult, analyze_market_structure
from app.core.config import get_settings
from app.core.db import get_session
from app.ingestion.store import store
from app.models.db_models import SignalRecord
from app.models.schemas import ConfluenceFactor, RiskPlan, TradeSignal, Venue

router = APIRouter(tags=["signals"])

MAX_SIGNAL_HISTORY_LIMIT = 500


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
async def get_signal(venue: str, symbol: str, timeframe: str = "1m") -> TradeSignal | None:
    candles = _load_candles(venue, symbol, timeframe)
    settings = get_settings()
    return generate_signal(
        candles,
        symbol=symbol,
        venue=Venue(venue),
        timeframe=timeframe,
        min_risk_reward=settings.min_risk_reward,
    )


@router.get("/signals/history", response_model=list[TradeSignal])
async def get_signal_history(
    venue: str,
    symbol: str,
    timeframe: str = "1m",
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[TradeSignal]:
    """Signals persisted by the background signal-watcher — a durable record of
    what the confluence engine has flagged over time, not just the current one."""
    limit = min(limit, MAX_SIGNAL_HISTORY_LIMIT)
    stmt = (
        select(SignalRecord)
        .where(
            SignalRecord.venue == venue,
            SignalRecord.symbol == symbol.lower(),
            SignalRecord.timeframe == timeframe,
        )
        .order_by(SignalRecord.ts.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        TradeSignal(
            symbol=r.symbol,
            venue=Venue(r.venue),
            timeframe=r.timeframe,
            direction=r.direction,
            ts=r.ts,
            confluences=[ConfluenceFactor(**f) for f in r.confluences],
            confluence_score=r.confluence_score,
            risk=RiskPlan(
                entry=r.entry,
                stop_loss=r.stop_loss,
                take_profits=r.take_profits,
                risk_reward=r.risk_reward,
                atr=r.atr,
            ),
            note=r.note,
        )
        for r in rows
    ]
