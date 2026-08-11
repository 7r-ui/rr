"""Smart Money Concepts market-structure detection.

Implements the definitions in `.claude/skills/market-structure-detection`
exactly: swing points confirmed n bars after they occur, an explicit
single-source-of-truth trend-state variable, BOS/CHoCH as closes beyond the
most recent confirmed swing (with/against trend respectively), order blocks
qualified by an ATR-multiple impulse threshold and tracked for mitigation,
FVGs tracked for fill percentage, and liquidity pools/sweeps distinguished
by a close-back requirement.

All thresholds are named parameters (see `SMCConfig`), not magic numbers.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app.models.schemas import (
    Candle,
    FairValueGap,
    LiquidityPool,
    LiquiditySweep,
    OrderBlock,
    StructureEvent,
    SwingPoint,
    TrendState,
)


@dataclass(frozen=True)
class SMCConfig:
    swing_lookback: int = 2  # n bars each side for swing confirmation
    atr_period: int = 14
    order_block_atr_multiple: float = 1.5  # k: impulse range >= k * ATR(n)
    liquidity_tolerance_pct: float = 0.05  # equal highs/lows tolerance, in percent
    sweep_lookahead: int = 3  # bars allowed for the close-back that confirms a sweep


class MarketStructureResult(BaseModel):
    trend_state: TrendState
    swing_points: list[SwingPoint]
    structure_events: list[StructureEvent]
    order_blocks: list[OrderBlock]
    fair_value_gaps: list[FairValueGap]
    liquidity_pools: list[LiquidityPool]
    liquidity_sweeps: list[LiquiditySweep]


def compute_atr(candles: list[Candle], period: int) -> list[float | None]:
    """True-range-based ATR, Wilder-smoothed. Index i is None until warmup completes."""
    atr: list[float | None] = [None] * len(candles)
    if len(candles) < period + 1:
        return atr

    trs: list[float] = []
    for i in range(1, len(candles)):
        c, prev = candles[i], candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
        trs.append(tr)

    first_atr = sum(trs[: period]) / period
    atr[period] = first_atr
    prev_atr = first_atr
    for i in range(period + 1, len(candles)):
        tr = trs[i - 1]
        prev_atr = (prev_atr * (period - 1) + tr) / period
        atr[i] = prev_atr
    return atr


def detect_swing_points(candles: list[Candle], n: int) -> list[SwingPoint]:
    """A confirmed swing high/low needs n bars on both sides, so nothing in the
    trailing n bars of the series can ever be reported here (repaint risk)."""
    points: list[SwingPoint] = []
    for i in range(n, len(candles) - n):
        window = candles[i - n : i + n + 1]
        c = candles[i]
        if c.high >= max(w.high for w in window):
            points.append(
                SwingPoint(index=i, ts=c.open_time, price=c.high, kind="high", confirmed=True)
            )
        if c.low <= min(w.low for w in window):
            points.append(
                SwingPoint(index=i, ts=c.open_time, price=c.low, kind="low", confirmed=True)
            )
    return points


def detect_structure_events(
    candles: list[Candle], swings: list[SwingPoint]
) -> tuple[TrendState, list[SwingPoint], list[StructureEvent]]:
    """Walks candles in order, maintaining one trend-state variable. A close beyond
    the most recent confirmed swing HIGH signals bullish structure; beyond the
    most recent confirmed swing LOW signals bearish. Whether that's a BOS or a
    CHoCH depends on whether it agrees with or flips the current trend state."""
    events: list[StructureEvent] = []
    trend = TrendState.UNDEFINED

    swings_by_index = sorted(swings, key=lambda s: s.index)
    last_confirmed_high: SwingPoint | None = None
    last_confirmed_low: SwingPoint | None = None
    broken_high_idx: int | None = None
    broken_low_idx: int | None = None
    swing_ptr = 0

    for i, c in enumerate(candles):
        while swing_ptr < len(swings_by_index) and swings_by_index[swing_ptr].index == i:
            s = swings_by_index[swing_ptr]
            if s.kind == "high":
                last_confirmed_high = s
            else:
                last_confirmed_low = s
            swing_ptr += 1

        if (
            last_confirmed_high is not None
            and c.close > last_confirmed_high.price
            and broken_high_idx != last_confirmed_high.index
        ):
            broken_high_idx = last_confirmed_high.index
            if trend in (TrendState.UP, TrendState.UNDEFINED):
                events.append(
                    StructureEvent(
                        kind="BOS" if trend == TrendState.UP else "CHoCH",
                        direction=TrendState.UP,
                        index=i,
                        ts=c.open_time,
                        price=c.close,
                        reference_swing=last_confirmed_high,
                        confidence=1.0,
                    )
                )
            else:
                events.append(
                    StructureEvent(
                        kind="CHoCH",
                        direction=TrendState.UP,
                        index=i,
                        ts=c.open_time,
                        price=c.close,
                        reference_swing=last_confirmed_high,
                        confidence=0.6,
                    )
                )
            trend = TrendState.UP

        elif (
            last_confirmed_low is not None
            and c.close < last_confirmed_low.price
            and broken_low_idx != last_confirmed_low.index
        ):
            broken_low_idx = last_confirmed_low.index
            if trend in (TrendState.DOWN, TrendState.UNDEFINED):
                events.append(
                    StructureEvent(
                        kind="BOS" if trend == TrendState.DOWN else "CHoCH",
                        direction=TrendState.DOWN,
                        index=i,
                        ts=c.open_time,
                        price=c.close,
                        reference_swing=last_confirmed_low,
                        confidence=1.0,
                    )
                )
            else:
                events.append(
                    StructureEvent(
                        kind="CHoCH",
                        direction=TrendState.DOWN,
                        index=i,
                        ts=c.open_time,
                        price=c.close,
                        reference_swing=last_confirmed_low,
                        confidence=0.6,
                    )
                )
            trend = TrendState.DOWN

    return trend, swings_by_index, events


def detect_order_blocks(
    candles: list[Candle],
    events: list[StructureEvent],
    atr: list[float | None],
    *,
    atr_multiple: float,
) -> list[OrderBlock]:
    """For each BOS/CHoCH, walk back from the event bar to find the last
    opposing-color candle before the impulse, qualifying the impulse against
    an ATR-multiple threshold so weak moves don't generate order blocks."""
    blocks: list[OrderBlock] = []

    for event in events:
        impulse_idx = event.index
        impulse = candles[impulse_idx]
        a = atr[impulse_idx]
        if a is None:
            continue
        impulse_range = impulse.high - impulse.low
        if impulse_range < atr_multiple * a:
            continue

        impulse_bullish = impulse.close >= impulse.open
        ob_idx = None
        for j in range(impulse_idx - 1, -1, -1):
            candle_bullish = candles[j].close >= candles[j].open
            if candle_bullish != impulse_bullish:
                ob_idx = j
                break
        if ob_idx is None:
            continue

        ob_candle = candles[ob_idx]
        top, bottom = max(ob_candle.open, ob_candle.close), min(ob_candle.open, ob_candle.close)

        mitigated = False
        mitigated_at = None
        for later in candles[ob_idx + 1 :]:
            if bottom <= later.low <= top or bottom <= later.high <= top or (
                later.low <= bottom and later.high >= top
            ):
                mitigated = True
                mitigated_at = later.open_time
                break

        blocks.append(
            OrderBlock(
                index=ob_idx,
                ts=ob_candle.open_time,
                direction=event.direction,
                top=top,
                bottom=bottom,
                origin_event=event.kind,
                mitigated=mitigated,
                mitigated_at=mitigated_at,
            )
        )
    return blocks


def detect_fair_value_gaps(candles: list[Candle]) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    for i in range(2, len(candles)):
        c1, c3 = candles[i - 2], candles[i]
        if c1.high < c3.low:
            gap = FairValueGap(
                index=i - 1,
                ts=candles[i - 1].open_time,
                direction=TrendState.UP,
                top=c3.low,
                bottom=c1.high,
            )
            gaps.append(gap)
        elif c1.low > c3.high:
            gap = FairValueGap(
                index=i - 1,
                ts=candles[i - 1].open_time,
                direction=TrendState.DOWN,
                top=c1.low,
                bottom=c3.high,
            )
            gaps.append(gap)

    for gap in gaps:
        span = gap.top - gap.bottom
        if span <= 0:
            continue
        deepest_fill = 0.0
        for later in candles[gap.index + 1 :]:
            overlap_top = min(later.high, gap.top)
            overlap_bottom = max(later.low, gap.bottom)
            if overlap_top <= overlap_bottom:
                continue
            if gap.direction == TrendState.UP:
                fill = (gap.top - overlap_bottom) / span
            else:
                fill = (overlap_top - gap.bottom) / span
            deepest_fill = max(deepest_fill, fill)
        gap.fill_pct = min(1.0, max(0.0, deepest_fill))
        gap.filled = gap.fill_pct >= 0.99
    return gaps


def detect_liquidity_pools(
    candles: list[Candle], swings: list[SwingPoint], *, tolerance_pct: float
) -> list[LiquidityPool]:
    pools: list[LiquidityPool] = []
    used = [False] * len(swings)
    for i, s in enumerate(swings):
        if used[i]:
            continue
        cluster = [i]
        for j in range(i + 1, len(swings)):
            if used[j] or swings[j].kind != s.kind:
                continue
            if abs(swings[j].price - s.price) / s.price * 100 <= tolerance_pct:
                cluster.append(j)
        if len(cluster) >= 2:
            for idx in cluster:
                used[idx] = True
            avg_price = sum(swings[idx].price for idx in cluster) / len(cluster)
            pools.append(
                LiquidityPool(
                    price=avg_price,
                    kind=s.kind,
                    touches=[swings[idx].index for idx in cluster],
                )
            )
    return pools


def detect_liquidity_sweeps(
    candles: list[Candle], pools: list[LiquidityPool], *, lookahead: int
) -> list[LiquiditySweep]:
    sweeps: list[LiquiditySweep] = []
    for pool in pools:
        last_touch = max(pool.touches)
        for i in range(last_touch + 1, len(candles)):
            c = candles[i]
            if pool.kind == "high" and c.high > pool.price:
                closed_back = any(
                    candles[k].close < pool.price
                    for k in range(i, min(i + lookahead, len(candles)))
                )
                sweeps.append(
                    LiquiditySweep(
                        pool=pool, index=i, ts=c.open_time, wick_price=c.high,
                        closed_back=closed_back,
                    )
                )
                break
            if pool.kind == "low" and c.low < pool.price:
                closed_back = any(
                    candles[k].close > pool.price
                    for k in range(i, min(i + lookahead, len(candles)))
                )
                sweeps.append(
                    LiquiditySweep(
                        pool=pool, index=i, ts=c.open_time, wick_price=c.low,
                        closed_back=closed_back,
                    )
                )
                break
    return sweeps


def analyze_market_structure(
    candles: list[Candle], config: SMCConfig | None = None
) -> MarketStructureResult:
    cfg = config or SMCConfig()
    atr = compute_atr(candles, cfg.atr_period)
    swings = detect_swing_points(candles, cfg.swing_lookback)
    trend, sorted_swings, events = detect_structure_events(candles, swings)
    order_blocks = detect_order_blocks(
        candles, events, atr, atr_multiple=cfg.order_block_atr_multiple
    )
    fvgs = detect_fair_value_gaps(candles)
    pools = detect_liquidity_pools(candles, sorted_swings, tolerance_pct=cfg.liquidity_tolerance_pct)
    sweeps = detect_liquidity_sweeps(candles, pools, lookahead=cfg.sweep_lookahead)

    return MarketStructureResult(
        trend_state=trend,
        swing_points=sorted_swings,
        structure_events=events,
        order_blocks=order_blocks,
        fair_value_gaps=fvgs,
        liquidity_pools=pools,
        liquidity_sweeps=sweeps,
    )
