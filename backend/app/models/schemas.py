"""Shared Pydantic contracts used across ingestion, analysis, vision and API layers."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Venue(str, Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OANDA = "oanda"
    POLYGON = "polygon"
    TRADINGVIEW = "tradingview"


class Candle(BaseModel):
    """A single OHLCV bar. `confirmed=False` means the bar is still forming (repaint risk)."""

    symbol: str
    venue: Venue
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    confirmed: bool = True


class Tick(BaseModel):
    symbol: str
    venue: Venue
    price: float
    size: float = 0.0
    ts: datetime


class TrendState(str, Enum):
    UP = "up"
    DOWN = "down"
    UNDEFINED = "undefined"


class SwingPoint(BaseModel):
    index: int
    ts: datetime
    price: float
    kind: str  # "high" | "low"
    confirmed: bool = True


class StructureEvent(BaseModel):
    """A BOS or CHoCH event."""

    kind: str  # "BOS" | "CHoCH"
    direction: TrendState
    index: int
    ts: datetime
    price: float
    reference_swing: SwingPoint
    confidence: float = Field(ge=0.0, le=1.0)


class OrderBlock(BaseModel):
    index: int
    ts: datetime
    direction: TrendState
    top: float
    bottom: float
    origin_event: str  # "BOS" | "CHoCH"
    mitigated: bool = False
    mitigated_at: Optional[datetime] = None


class FairValueGap(BaseModel):
    index: int
    ts: datetime
    direction: TrendState
    top: float
    bottom: float
    fill_pct: float = 0.0
    filled: bool = False


class LiquidityPool(BaseModel):
    price: float
    kind: str  # "high" | "low"
    touches: list[int]


class LiquiditySweep(BaseModel):
    pool: LiquidityPool
    index: int
    ts: datetime
    wick_price: float
    closed_back: bool


class ElliottWaveLabel(BaseModel):
    index: int
    ts: datetime
    price: float
    label: str  # "1".."5", "A".."C"
    degree: str = "minor"
    confidence: float = Field(ge=0.0, le=1.0)


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class ConfluenceFactor(BaseModel):
    school: str  # "smc" | "elliott" | "liquidity"
    description: str
    weight: float = 1.0


class RiskPlan(BaseModel):
    entry: float
    stop_loss: float
    take_profits: list[float]
    risk_reward: list[float]
    atr: float
    account_balance: float
    risk_pct: float
    risk_amount: float
    position_size: float  # units of the base asset sized so risk_amount is the max loss to stop_loss


class TradeSignal(BaseModel):
    symbol: str
    venue: Venue
    timeframe: str
    direction: SignalDirection
    ts: datetime
    confluences: list[ConfluenceFactor]
    confluence_score: float
    risk: RiskPlan
    note: Optional[str] = None


class ChartAnalysisRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    price_axis_hint: Optional[tuple[float, float]] = None  # (price_at_top, price_at_bottom)
    time_axis_hint: Optional[tuple[str, str]] = None  # (iso_start, iso_end)


class DetectedLevel(BaseModel):
    label: str  # "support" | "resistance" | "order_block" | "fvg" | "trendline"
    price: Optional[float] = None
    price_range: Optional[tuple[float, float]] = None
    pixel_bbox: tuple[int, int, int, int]
    confidence: float = Field(ge=0.0, le=1.0)


class ChartAnalysisResponse(BaseModel):
    symbol: Optional[str]
    levels: list[DetectedLevel]
    notes: str


class MarketStructureSection(BaseModel):
    trend: str  # "bullish" | "bearish" | "sideways"
    key_structure: list[str]


class TradeSetupSection(BaseModel):
    bias: str  # "bullish" | "bearish" | "neutral"
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profits: list[float] = []


class RiskManagementSection(BaseModel):
    account_balance: float
    risk_pct: float
    max_risk_amount: float
    position_size: Optional[float] = None
    risk_reward: Optional[float] = None


class ConvictionSection(BaseModel):
    confidence: str  # "High" | "Medium" | "Low"
    reasoning: list[str]


class ChartReport(BaseModel):
    """The structured SMC/Price-Action report an LLM (Claude or an
    OpenAI-compatible vision model) produces from one chart screenshot —
    a technical read, not individualized investment advice."""

    symbol: Optional[str] = None
    market_structure: MarketStructureSection
    trade_setup: TradeSetupSection
    risk_management: RiskManagementSection
    conviction: ConvictionSection
    provider: str


class TradingViewAlertPayload(BaseModel):
    """Body of a TradingView `alert()` webhook (configured via a Pine Script
    `alert_message` using placeholders like {{open}}/{{high}}/{{low}}/{{close}}/{{volume}}/{{time}})."""

    symbol: str
    timeframe: str = "1m"
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    time: Optional[datetime] = None
