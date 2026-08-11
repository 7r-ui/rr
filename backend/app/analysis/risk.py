"""ATR-based stop loss + multi-target take profit, gated by a minimum R:R.

This is a technical risk-sizing calculation, not individualized investment
advice: it turns an entry price + direction + ATR into a structured plan,
nothing more.
"""
from __future__ import annotations

from app.analysis.smc import compute_atr
from app.models.schemas import Candle, RiskPlan, SignalDirection


def build_risk_plan(
    candles: list[Candle],
    entry: float,
    direction: SignalDirection,
    *,
    atr_period: int = 14,
    stop_atr_multiple: float = 1.5,
    take_profit_multiples: tuple[float, ...] = (2.0, 3.0, 4.0),
    min_risk_reward: float = 2.0,
) -> RiskPlan | None:
    """Returns None if there isn't enough history for ATR, or if the resulting
    plan can't clear `min_risk_reward` on its nearest target."""
    atr_series = compute_atr(candles, atr_period)
    atr = atr_series[-1] if atr_series else None
    if atr is None or atr <= 0:
        return None

    stop_distance = stop_atr_multiple * atr
    if direction == SignalDirection.LONG:
        stop_loss = entry - stop_distance
        take_profits = [entry + m * stop_distance for m in take_profit_multiples]
    else:
        stop_loss = entry + stop_distance
        take_profits = [entry - m * stop_distance for m in take_profit_multiples]

    risk = abs(entry - stop_loss)
    if risk <= 0:
        return None

    rr = [abs(tp - entry) / risk for tp in take_profits]
    if not rr or rr[0] < min_risk_reward:
        return None

    return RiskPlan(
        entry=entry, stop_loss=stop_loss, take_profits=take_profits, risk_reward=rr, atr=atr
    )
