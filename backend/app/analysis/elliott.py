"""Elliott Wave heuristic tracking.

This is pattern-matching over zigzag pivots, not a rigorous wave-count
solver — Elliott counts are inherently ambiguous, so every label carries an
explicit confidence score derived from how well the classic impulse rules
hold, and this is meant to be ONE confluence factor among several, never a
standalone signal.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Candle, ElliottWaveLabel, SwingPoint


@dataclass(frozen=True)
class ElliottConfig:
    min_pivot_move_pct: float = 0.5  # filters noise pivots out of the zigzag


def _zigzag_pivots(swings: list[SwingPoint], min_move_pct: float) -> list[SwingPoint]:
    """Collapses raw swing points into an alternating high/low zigzag, dropping
    pivots that don't represent at least `min_move_pct` move from the prior one."""
    ordered = sorted(swings, key=lambda s: s.index)
    pivots: list[SwingPoint] = []
    for s in ordered:
        if not pivots:
            pivots.append(s)
            continue
        last = pivots[-1]
        if s.kind == last.kind:
            keep_new = (s.price > last.price) if s.kind == "high" else (s.price < last.price)
            if keep_new:
                pivots[-1] = s
            continue
        move_pct = abs(s.price - last.price) / last.price * 100
        if move_pct < min_move_pct:
            continue
        pivots.append(s)
    return pivots


def _score_impulse(pivots: list[SwingPoint]) -> float:
    """pivots[0..5] = start, wave1 end, wave2 end, wave3 end, wave4 end, wave5 end."""
    if len(pivots) != 6:
        return 0.0
    p0, p1, p2, p3, p4, p5 = (p.price for p in pivots)
    up = p1 > p0
    score = 1.0

    wave1 = abs(p1 - p0)
    wave3 = abs(p3 - p2)

    # Rule: wave 2 never retraces beyond the start of wave 1.
    if up and p2 < p0:
        score -= 0.4
    if not up and p2 > p0:
        score -= 0.4

    # Rule: wave 3 is never the shortest among 1, 3, 5.
    wave5 = abs(p5 - p4)
    if wave3 < wave1 and wave3 < wave5:
        score -= 0.3

    # Rule: wave 4 doesn't overlap wave 1's price territory (non-overlap, common case).
    if up and p4 < p1:
        score -= 0.3
    if not up and p4 > p1:
        score -= 0.3

    return max(0.0, score)


def label_elliott_waves(
    candles: list[Candle], swings: list[SwingPoint], config: ElliottConfig | None = None
) -> list[ElliottWaveLabel]:
    cfg = config or ElliottConfig()
    pivots = _zigzag_pivots(swings, cfg.min_pivot_move_pct)
    if len(pivots) < 6:
        return []

    labels: list[ElliottWaveLabel] = []
    window = pivots[-6:]
    confidence = _score_impulse(window)
    impulse_tags = ["0", "1", "2", "3", "4", "5"]
    for pivot, tag in zip(window, impulse_tags):
        labels.append(
            ElliottWaveLabel(
                index=pivot.index,
                ts=pivot.ts,
                price=pivot.price,
                label=tag,
                degree="minor",
                confidence=confidence,
            )
        )

    corrective_tags = ["A", "B", "C"]
    for pivot, tag in zip(pivots[-3:] if len(pivots) >= 9 else [], corrective_tags):
        labels.append(
            ElliottWaveLabel(
                index=pivot.index, ts=pivot.ts, price=pivot.price, label=tag,
                degree="minor", confidence=confidence * 0.7,
            )
        )

    return labels
