# NexusTrade AI — MCP Server

An MCP (Model Context Protocol) server that exposes the NexusTrade AI
backend — SMC/Elliott-Wave confluence signals, ATR-based risk management,
and the Claude-powered chart-screenshot report — as tools Claude Desktop or
Claude Code can call directly over stdio.

This is a technical/quantitative-analysis aid, not a source of
individualized financial or investment advice.

## Tools

| Tool | Backend route | Notes |
|---|---|---|
| `list_market_symbols` | `GET /market/symbols` | What venue/symbol/timeframe combos currently have cached candles. Call this first. |
| `get_market_structure` | `GET /structure` | Trend state, swing points, BOS/CHoCH, order blocks, FVGs, liquidity pools/sweeps. Trims list fields to the most recent `max_items` (default 20). |
| `get_trade_signal` | `GET /signals` | The confluence signal (or none) with the full risk plan, including `position_size`. |
| `notify_trade_signal` | `POST /signals/notify` | Same as above, but also pushes to Telegram/Discord if configured. Side-effecting. |
| `analyze_chart_report` | `POST /analyze-chart/report` | Uploads a local chart screenshot (by path), returns the structured SMC report. |
| `send_tradingview_alert` | `POST /webhook/tradingview` | Feeds one OHLCV bar in as if from a TradingView alert; useful for backfill/testing. |
| `check_backend_status` | `GET /health` | Diagnostic: is the backend reachable, and what URL is this server configured to hit. |

## Install

```bash
cd mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run standalone

The backend (`backend/`) must be running separately — see the root
`README.md` for `docker compose up` / `uvicorn` instructions.

```bash
export NEXUSTRADE_BACKEND_URL=http://localhost:8000   # default, can be omitted
python server.py
```

This starts the server on stdio and blocks, waiting for an MCP client to
connect — it's not meant to be run interactively on its own; use a client
(below) or the `mcp` CLI's dev inspector to exercise it.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEXUSTRADE_BACKEND_URL` | `http://localhost:8000` | Base URL of the running FastAPI backend. |
| `NEXUSTRADE_WEBHOOK_SECRET` | unset | Fallback value for `send_tradingview_alert`'s `secret` argument when the caller doesn't pass one. Only relevant if the backend has `TRADINGVIEW_WEBHOOK_SECRET` set. |

## Claude Desktop / Claude Code configuration

Add to your MCP servers config (`claude_desktop_config.json` for Claude
Desktop, or the equivalent `mcp_servers` entry for Claude Code):

```json
{
  "mcpServers": {
    "nexustrade": {
      "command": "python",
      "args": ["/absolute/path/to/rr/mcp-server/server.py"],
      "env": {
        "NEXUSTRADE_BACKEND_URL": "http://localhost:8000"
      }
    }
  }
}
```

If you installed dependencies into a virtualenv rather than system Python,
point `command` at that venv's interpreter instead, e.g.
`/absolute/path/to/rr/mcp-server/.venv/bin/python`.

## Error handling

Every tool catches connection failures, timeouts, and non-2xx backend
responses (404s from unwarmed ingestion, 401s from a bad webhook secret,
503s from `analyze_chart_report` when no vision provider is configured,
etc.) and returns `{"error": "<message>"}` as its result text rather than
raising — the MCP server process itself never crashes because the backend
is down or misconfigured.
