# NexusTrade AI

A real-time financial analysis platform: live crypto/forex market data,
an SMC (Smart Money Concepts) + Elliott Wave confluence signal engine with
ATR-based risk management, and an AI vision endpoint that reads chart
screenshots.

This is a technical/quantitative-analysis tool, not a source of
individualized investment advice.

## Architecture

```
backend/            FastAPI application
  app/ingestion/     Binance & Bybit WebSocket kline streams,
                     OANDA (streaming) and Polygon.io (WebSocket) forex/metals
                     clients, an in-memory rolling candle store synced off
                     Redis Pub/Sub
  app/analysis/      smc.py     — swing points, trend state, BOS/CHoCH,
                                  order blocks (with mitigation tracking),
                                  fair value gaps (with fill tracking),
                                  liquidity pools/sweeps
                     elliott.py — zigzag-pivot Elliott wave heuristic labeler
                     risk.py    — ATR-based stop loss + multi-target take
                                  profit, gated by a minimum risk:reward
                     confluence.py — combines SMC + liquidity + Elliott;
                                  only emits a signal when >= 2 distinct
                                  schools agree on direction AND the risk
                                  plan clears the minimum R:R (default 1:2)
  app/vision/        OpenCV Hough-transform level detection (parser.py) +
                     a pluggable multimodal vision model client
                     (model_client.py, OpenAI-compatible, gpt-4o-mini by
                     default) for the /analyze-chart endpoint
  app/api/routes/    market.py (REST + WebSocket candle fan-out),
                     signals.py (/structure, /signals, POST /signals/notify),
                     chart.py (/analyze-chart, POST /analyze-chart/report),
                     webhook.py (POST /webhook/tradingview)
  app/alerts/        dispatcher.py — best-effort Telegram/Discord delivery
                     for a generated TradeSignal (opt-in via env, never
                     raises on a channel being down)

mcp-server/          Python MCP server exposing this backend's market
                     structure / signal / chart-report endpoints as tools
                     for Claude Desktop/Code — see mcp-server/README.md

pine/                TradingView Pine Script companion that fires
                     `alert()` webhooks with OHLCV JSON at
                     POST /webhook/tradingview, so a symbol doesn't need a
                     dedicated exchange feed wired into app/ingestion

frontend/            Next.js 15 (App Router) + TypeScript + Tailwind
                     dashboard: glassmorphism UI, TradingView
                     Lightweight Charts candlestick panel with live
                     WebSocket updates, confluence signal panel, and a
                     chart-screenshot uploader for the vision endpoint

docker-compose.yml   redis + backend + frontend
```

Ingestion publishes to Redis Pub/Sub channels (`candles:*`, `ticks:*`); the
analysis layer and the API's WebSocket fan-out both subscribe independently,
so one exchange feed stalling never blocks another.

## Definitions used by the SMC engine

Implemented exactly per `.claude/skills/market-structure-detection`: swing
points confirm `n` bars after they occur (no repainting the trailing edge),
a single trend-state variable, BOS = close beyond the last confirmed swing
*with* the trend, CHoCH = close beyond it *against* the trend (lower
confidence, flips the trend state), order blocks qualified by an ATR-multiple
impulse threshold and tracked for mitigation over time, FVGs tracked for
fill percentage, and liquidity sweeps distinguished from breakouts by a
close-back requirement.

## Running locally

### With Docker Compose

```bash
cp backend/.env.example backend/.env   # fill in API keys you have; all are optional
docker compose up --build
```

Backend: http://localhost:8000/docs · Frontend: http://localhost:3000

### Without Docker

```bash
# Redis
redis-server &

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## What's real vs. what needs your own API keys

- **Binance & Bybit** kline streams work out of the box — public endpoints,
  no key required.
- **OANDA** (forex/metals streaming) and **Polygon.io** (forex/metals
  WebSocket) clients are fully implemented but stay idle until you supply
  `OANDA_API_KEY`/`OANDA_ACCOUNT_ID` or `POLYGON_API_KEY` — the rest of the
  platform keeps running without them.
- **Vision chart parser**: the OpenCV edge/Hough-transform level detector
  always runs. The multimodal model call (gpt-4o-mini by default) is
  pluggable and only activates with `OPENAI_API_KEY` set; without it,
  `/analyze-chart` still returns the OpenCV-only levels.
- **Elliott Wave labeling** is a heuristic zigzag-pivot pattern matcher, not
  a rigorous wave-count solver — it's one confluence input among several,
  weighted by how well the classic impulse rules (wave 2 doesn't retrace
  past wave 1's start, wave 3 isn't the shortest, wave 4 doesn't overlap
  wave 1) hold for the current pivots.
- Message broker is Redis Pub/Sub, not Kafka — sufficient for this scale;
  swap in `aiokafka` behind the same publish/subscribe interface in
  `app/core/redis_bus.py` if you need Kafka's durability/replay guarantees.

## Position sizing, alerts, TradingView webhooks, and the Claude report

- **Position sizing**: `RiskPlan` (and the `/signals` response) now includes
  `account_balance`, `risk_pct`, `risk_amount`, and `position_size` —
  sized so a stop-loss hit loses exactly `risk_amount` (default 1% of a
  $10,000 account, overridable per-request via `?account_balance=` /
  `?risk_pct=`, or globally via `DEFAULT_ACCOUNT_BALANCE`/`DEFAULT_RISK_PCT`).
- **Claude-powered structured report**: `POST /analyze-chart/report` (image
  upload) runs the full SMC/Price-Action analyst prompt against Claude
  (`ANTHROPIC_API_KEY`, preferred) or an OpenAI-compatible vision model
  (`OPENAI_API_KEY` fallback), returning `market_structure`, `trade_setup`,
  `risk_management` (computed server-side from the model's entry/stop, never
  invented by the model), and `conviction`. Returns 503 — never a fabricated
  report — if no provider is configured or the response doesn't parse.
- **Alerts**: `POST /signals/notify` runs the same confluence logic as
  `GET /signals` and, if a signal fires, pushes a formatted message to
  Telegram (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`) and/or Discord
  (`DISCORD_WEBHOOK_URL`) — either left blank is simply skipped.
- **TradingView webhook ingestion**: `POST /webhook/tradingview` accepts an
  `alert()` webhook body (`symbol`, `timeframe`, `open/high/low/close`,
  `volume`, optional `time`) and feeds it into the same candle store/Redis
  pub-sub pipeline as the exchange WS feeds — see `pine/` for the companion
  script. Set `TRADINGVIEW_WEBHOOK_SECRET` and require it as `?secret=` or
  an `X-Webhook-Secret` header; left blank, the endpoint accepts
  unauthenticated data (local dev only).

## Known limitation

`next@15.5.21`'s optional `sharp` image-optimization dependency and its
vendored `postcss` currently resolve to versions with open advisories
(`npm audit`). This app doesn't use `next/image`, so the vulnerable code
path isn't exercised, but a Next 16 + React 19 upgrade would clear it —
deferred here pending a compatibility pass on the rest of the stack.
