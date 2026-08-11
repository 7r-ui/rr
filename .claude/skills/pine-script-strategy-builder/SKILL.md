---
name: pine-script-strategy-builder
description: Use when scaffolding a new TradingView Pine Script (v5/v6) indicator or strategy from scratch — establishes the standard skeleton (inputs, signal logic, plotting, alerts, strategy order calls, backtest settings) so new scripts start from a consistent, backtest-honest template.
---

# Pine Script Strategy Builder

This skill provides the standard skeleton for a new Pine Script indicator or
strategy, so scripts in this repo start consistent rather than reinventing
structure each time. Pair with `market-structure-detection` when the script
implements SMC-style logic, and hand off to the `pine-script-developer` agent
for full implementation.

## Skeleton — indicator (signal/visualization only, no simulated orders)

```pine
//@version=6
indicator("Name", overlay=true, max_lines_count=500, max_boxes_count=500)

// --- Inputs, grouped ---
grp_signal = "Signal Settings"
lookback = input.int(2, "Swing Lookback", minval=1, group=grp_signal)

// --- Signal logic ---
// ... compute here, using confirmed (non-repainting) values only ...

// --- Plotting ---
plotshape(condition, style=shape.triangleup, location=location.belowbar)

// --- Alerts ---
alertcondition(condition, title="Signal", message="{{ticker}} signal fired")
```

## Skeleton — strategy (simulated orders, for backtesting)

```pine
//@version=6
strategy("Name", overlay=true,
     default_qty_type=strategy.percent_of_equity, default_qty_value=1,
     commission_type=strategy.commission.percent, commission_value=0.05,
     slippage=2, calc_on_every_tick=false)

// --- Inputs ---
riskPct = input.float(1.0, "Risk % per trade", minval=0.1, maxval=10)

// --- Entry/exit logic ---
if (longCondition)
    strategy.entry("Long", strategy.long)
if (shortCondition)
    strategy.entry("Short", strategy.short)

stopPrice = ...
targetPrice = ...
strategy.exit("Exit Long", "Long", stop=stopPrice, limit=targetPrice)
```

## Checklist before handing a script back

- [ ] `//@version=6` (or the version already used by the file being edited).
- [ ] Inputs are grouped (`group=`) and have sane `minval`/`maxval`.
- [ ] Strategy scripts declare `commission_type`/`commission_value` and
      `slippage` explicitly — never rely on Pine's silent defaults.
- [ ] Every actionable signal has a matching `alertcondition()` or
      `alert()` call, so it can drive webhook automation.
- [ ] No `request.security` call without an explicit
      `barmerge.lookahead_off` (or a documented reason for lookahead-on).
- [ ] Comments only where Pine's execution model is non-obvious — not
      restating what the code already says.
