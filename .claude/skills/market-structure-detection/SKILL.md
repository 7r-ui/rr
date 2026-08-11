---
name: market-structure-detection
description: Use when implementing automated market-structure / order-flow detection — swing points, break of structure (BOS), change of character (CHoCH), order blocks, fair value gaps, and liquidity sweeps — in code (Python, Pine Script, or similar). Load this before writing detection logic so definitions and edge cases stay consistent across the codebase.
---

# Market Structure Detection

This skill defines precise, implementation-ready rules for common
smart-money-concepts (SMC) style market-structure primitives, so that
detection logic is consistent wherever it's implemented in this repo. It is
a technical/quantitative-analysis skill, not investment advice.

## Definitions to implement exactly

### Swing high / swing low
A bar `i` is a swing high if its high is the maximum among `[i-n, i+n]`
(n bars each side, `n` a tunable parameter, default 2). Swing low is the
mirror on lows. Swing points are only confirmed `n` bars after they occur —
never treat the most recent `n` bars as having a confirmed swing.

### Trend state
Maintain an explicit trend-state variable (`up`, `down`, or `undefined` at
start): a sequence of higher-highs/higher-lows is `up`; lower-highs/lower-lows
is `down`.

### Break of Structure (BOS)
A close beyond the most recent confirmed swing point **in the direction of**
the current trend state. Confirms trend continuation.

### Change of Character (CHoCH)
A close beyond the most recent confirmed swing point **against** the current
trend state. This flips the trend-state variable and is the first signal a
reversal may be underway — treat it as lower-confidence than a BOS in the
prevailing direction.

### Order block
The last opposing-color candle immediately before the impulse candle(s) that
produced a BOS or CHoCH. Qualify the impulse with an explicit threshold
(e.g., candle range ≥ `k` × ATR(n), default k=1.5) so weak moves don't
generate order blocks. An order block is considered "mitigated" once price
returns into its range — track mitigation state, don't just plot it once.

### Fair value gap (FVG) / imbalance
For three consecutive candles, a bullish FVG exists when candle 1's high is
below candle 3's low (the gap is `[candle1.high, candle3.low]`); bearish is
the mirror. Track fill percentage as price re-enters the gap.

### Liquidity pools and sweeps
Equal (within a tolerance, e.g. 0.05%) highs or lows mark a liquidity pool.
A sweep is a wick that trades beyond the pool level and then closes back on
the origin side within the same or next few bars — the close-back is what
distinguishes a sweep from a genuine breakout.

## Implementation checklist

- [ ] All thresholds (`n`, ATR multiple, tolerance %) are named parameters,
      not magic numbers.
- [ ] Every construct states whether it's confirmed-on-close or provisional
      on the current unclosed bar (repaint risk).
- [ ] Order blocks and FVGs track mitigation/fill state over time, not just
      a one-time plot.
- [ ] Trend-state is a single source of truth other logic reads from, not
      recomputed inconsistently in multiple places.
- [ ] Output is structured (objects/dataclasses or Pine `type`s), not just
      chart drawings, so it can feed downstream strategy or alert logic.

## Related agents

For applying this skill to a specific target language, hand off to
`market-structure-analyst` (design/logic), `pine-script-developer`
(TradingView implementation), or `quant-backtest-engineer` (Python/backtest
implementation) under `.claude/agents/quant-trading/`.
