"""Multi-school confluence signal engine.

Per the spec: "signals are triggered only when multi-school confluences
align." A single BOS or a single Elliott label is never enough — this
requires agreement across at least two distinct analytical schools (SMC
structure, liquidity, Elliott) on the same direction before it will emit a
TradeSignal, and every emitted signal must clear the configured minimum
risk:reward (default 1:2) via `risk.build_risk_plan`.
"""
from __future__ import annotations

from app.analysis.elliott import label_elliott_waves
from app.analysis.risk import build_risk_plan
from app.analysis.smc import SMCConfig, analyze_market_structure
from app.models.schemas import (
    Candle,
    ConfluenceFactor,
    SignalDirection,
    TradeSignal,
    TrendState,
    Venue,
)

MIN_DISTINCT_SCHOOLS = 2


def _direction_from_trend(trend: TrendState) -> SignalDirection | None:
    if trend == TrendState.UP:
        return SignalDirection.LONG
    if trend == TrendState.DOWN:
        return SignalDirection.SHORT
    return None


def generate_signal(
    candles: list[Candle],
    *,
    symbol: str,
    venue: Venue,
    timeframe: str,
    smc_config: SMCConfig | None = None,
    min_risk_reward: float = 2.0,
) -> TradeSignal | None:
    if len(candles) < 30:
        return None

    structure = analyze_market_structure(candles, smc_config)
    elliott_labels = label_elliott_waves(candles, structure.swing_points)

    factors: list[ConfluenceFactor] = []
    schools: set[str] = set()
    directions: list[SignalDirection] = []

    if structure.structure_events:
        latest_event = structure.structure_events[-1]
        direction = _direction_from_trend(latest_event.direction)
        if direction is not None:
            directions.append(direction)
            schools.add("smc")
            factors.append(
                ConfluenceFactor(
                    school="smc",
                    description=f"{latest_event.kind} confirming {latest_event.direction.value} structure",
                    weight=1.0 if latest_event.kind == "BOS" else 0.6,
                )
            )

    recent_sweeps = [s for s in structure.liquidity_sweeps if s.closed_back]
    if recent_sweeps:
        last_sweep = recent_sweeps[-1]
        sweep_direction = (
            SignalDirection.LONG if last_sweep.pool.kind == "low" else SignalDirection.SHORT
        )
        directions.append(sweep_direction)
        schools.add("liquidity")
        factors.append(
            ConfluenceFactor(
                school="liquidity",
                description=f"Liquidity sweep of {last_sweep.pool.kind} pool with close-back",
                weight=0.8,
            )
        )

    unmitigated_obs = [ob for ob in structure.order_blocks if not ob.mitigated]
    if unmitigated_obs:
        last_ob = unmitigated_obs[-1]
        ob_direction = _direction_from_trend(last_ob.direction)
        if ob_direction is not None:
            directions.append(ob_direction)
            schools.add("smc")
            factors.append(
                ConfluenceFactor(
                    school="smc",
                    description=f"Unmitigated {last_ob.direction.value} order block from {last_ob.origin_event}",
                    weight=0.7,
                )
            )

    if elliott_labels:
        last_label = elliott_labels[-1]
        if last_label.confidence > 0.3 and len(elliott_labels) >= 2:
            prior = elliott_labels[-2]
            wave_direction = (
                SignalDirection.LONG if last_label.price > prior.price else SignalDirection.SHORT
            )
            directions.append(wave_direction)
            schools.add("elliott")
            factors.append(
                ConfluenceFactor(
                    school="elliott",
                    description=f"Wave {last_label.label} count, confidence {last_label.confidence:.2f}",
                    weight=last_label.confidence,
                )
            )

    if len(schools) < MIN_DISTINCT_SCHOOLS or not directions:
        return None

    long_votes = directions.count(SignalDirection.LONG)
    short_votes = directions.count(SignalDirection.SHORT)
    if long_votes == short_votes:
        return None
    final_direction = SignalDirection.LONG if long_votes > short_votes else SignalDirection.SHORT

    # `directions` and `factors` were appended in lockstep above, so zipping
    # them recovers which factor voted for which direction.
    aligned = [
        (school_factor, vote)
        for school_factor, vote in zip(factors, directions)
        if vote == final_direction
    ]
    aligned_factors = [f for f, _ in aligned]
    aligned_schools = {f.school for f in aligned_factors}
    if len(aligned_schools) < MIN_DISTINCT_SCHOOLS:
        return None

    entry = candles[-1].close
    risk_plan = build_risk_plan(
        candles, entry, final_direction, min_risk_reward=min_risk_reward
    )
    if risk_plan is None:
        return None

    confluence_score = sum(f.weight for f in aligned_factors) / max(len(aligned_factors), 1)

    return TradeSignal(
        symbol=symbol,
        venue=venue,
        timeframe=timeframe,
        direction=final_direction,
        ts=candles[-1].open_time,
        confluences=aligned_factors,
        confluence_score=round(min(confluence_score, 1.0), 3),
        risk=risk_plan,
        note=f"{len(aligned_schools)} schools aligned: {', '.join(sorted(aligned_schools))}",
    )
