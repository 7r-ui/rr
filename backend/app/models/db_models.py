"""SQLAlchemy ORM models for the durable persistence layer.

Kept separate from `app/models/schemas.py` (the Pydantic wire contracts) on
purpose — the DB shape and the API shape are allowed to diverge without
forcing changes in both places.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CandleRecord(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("venue", "symbol", "timeframe", "open_time", name="uq_candle_key"),
        Index("ix_candle_lookup", "venue", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SignalRecord(Base):
    __tablename__ = "signals"
    __table_args__ = (Index("ix_signal_lookup", "venue", "symbol", "timeframe", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confluence_score: Mapped[float] = mapped_column(Float, nullable=False)
    confluences: Mapped[list] = mapped_column(JSON, nullable=False)
    entry: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profits: Mapped[list] = mapped_column(JSON, nullable=False)
    risk_reward: Mapped[list] = mapped_column(JSON, nullable=False)
    atr: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
