#!/usr/bin/env python3
"""MCP server for NexusTrade AI.

Exposes the NexusTrade AI FastAPI backend (Smart-Money-Concepts /
Elliott-Wave confluence signal engine, ATR-based risk management, and a
chart-screenshot vision report) as a small set of MCP tools over stdio, so
Claude Desktop / Claude Code can query live market structure, pull
confluence trade signals with a full position-sizing plan, request a
structured SMC report from a TradingView screenshot, and backfill candle
data via the TradingView webhook path.

This tool surface is a technical/quantitative-analysis aid, not a source of
individualized financial or investment advice.

Configuration (environment variables):
    NEXUSTRADE_BACKEND_URL     Base URL of the running backend.
                                Default: http://localhost:8000
    NEXUSTRADE_WEBHOOK_SECRET  Fallback TradingView webhook shared secret,
                                used by send_tradingview_alert when the
                                caller doesn't pass one explicitly. Optional.
"""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Literal, Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nexustrade_mcp")

BACKEND_URL = os.environ.get("NEXUSTRADE_BACKEND_URL", "http://localhost:8000").rstrip("/")
WEBHOOK_SECRET = os.environ.get("NEXUSTRADE_WEBHOOK_SECRET") or None

# Confluence/structure calls hit an in-memory candle store and are fast; the
# chart-report call runs a multimodal vision model round trip and can take
# much longer.
DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
REPORT_TIMEOUT = httpx.Timeout(90.0, connect=5.0)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # mirrors backend's app/api/routes/chart.py limit

Venue = Literal["binance", "bybit", "oanda", "polygon", "tradingview"]


class BackendError(Exception):
    """Raised whenever the NexusTrade backend can't be reached or returns an error.

    Caught at the top of every tool so a bad backend response or a network
    hiccup turns into a clear message returned to the model, instead of an
    uncaught exception that would crash the MCP server process.
    """


def _clean(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drops None-valued keys so unset optional args aren't sent as literal query params."""
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None}


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:500] or f"HTTP {response.status_code}"
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail)
    return json.dumps(body)[:500]


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
) -> httpx.Response:
    """Shared HTTP helper used by every tool. Raises BackendError on any
    connectivity failure, timeout, or non-2xx response, with a message
    suitable for showing directly to the model."""
    url = f"{BACKEND_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, params=_clean(params), json=json_body, data=data, files=files
            )
    except httpx.ConnectError as exc:
        raise BackendError(
            f"Could not connect to the NexusTrade backend at {BACKEND_URL}. "
            f"Is it running (uvicorn app.main:app), and is NEXUSTRADE_BACKEND_URL correct? ({exc})"
        ) from exc
    except httpx.TimeoutException as exc:
        raise BackendError(
            f"Request to {url} timed out after {timeout.read}s. "
            "The backend may be overloaded, or ingestion may still be warming up."
        ) from exc
    except httpx.HTTPError as exc:
        raise BackendError(f"HTTP error calling {url}: {exc}") from exc

    if response.status_code >= 400:
        raise BackendError(
            f"NexusTrade backend returned HTTP {response.status_code} for {method} {path}: "
            f"{_extract_detail(response)}"
        )
    return response


def _ok(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(message: str) -> str:
    return json.dumps({"error": message}, indent=2)


def _trim(items: list[Any], max_items: int) -> tuple[list[Any], int]:
    """Keeps the most recent `max_items` entries of a chronologically
    ordered list, returning (trimmed_list, original_count)."""
    total = len(items)
    if max_items <= 0 or total <= max_items:
        return items, total
    return items[-max_items:], total


@mcp.tool(
    title="List Market Symbols",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def list_market_symbols() -> str:
    """List every venue/symbol/timeframe combination the backend currently has
    candle data cached for (from live exchange ingestion and/or TradingView
    webhook backfill). Call this first if you don't already know a valid
    (venue, symbol, timeframe) triple to pass to get_market_structure,
    get_trade_signal, or notify_trade_signal — those will 404 with "no cached
    candles yet" for a combination that isn't in this list.

    Returns:
        JSON array of {"venue": str, "symbol": str, "timeframe": str}.
        Empty array means ingestion hasn't produced any candles yet (may
        still be warming up), or nothing has been backfilled via the
        TradingView webhook.

        On failure: {"error": "<message>"}.
    """
    try:
        response = await _request("GET", "/market/symbols")
        return _ok(response.json())
    except BackendError as exc:
        return _err(str(exc))


@mcp.tool(
    title="Get Market Structure",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def get_market_structure(
    venue: Venue,
    symbol: str,
    timeframe: str = "1m",
    max_items: int = 20,
) -> str:
    """Get the Smart-Money-Concepts market structure read for one
    venue/symbol/timeframe: current trend state, confirmed swing highs/lows,
    Break-of-Structure / Change-of-Character events, order blocks (with
    mitigation status), fair value gaps (with fill %), and liquidity
    pools/sweeps. This is the raw structural analysis; use get_trade_signal
    for the actionable confluence signal derived from it.

    Args:
        venue: One of "binance", "bybit", "oanda", "polygon", "tradingview".
        symbol: Exchange-native symbol, e.g. "btcusdt" (Binance/Bybit) or
            "EUR_USD" (OANDA/Polygon/TradingView-backfilled).
        timeframe: Candle interval as ingested, e.g. "1m", "5m", "15m", "1h".
            Default "1m".
        max_items: Cap on how many of the most recent entries to return per
            list field (swing_points, structure_events, order_blocks,
            fair_value_gaps, liquidity_pools, liquidity_sweeps), to avoid
            dumping a large, mostly-irrelevant history. Set to 0 for no
            limit. Default 20.

    Returns:
        JSON object:
        {
            "trend_state": "up" | "down" | "undefined",
            "swing_points": [...],        # most recent `max_items`, oldest->newest
            "swing_points_total": int,    # count before trimming
            "structure_events": [...],    # BOS/CHoCH events
            "structure_events_total": int,
            "order_blocks": [...],
            "order_blocks_total": int,
            "fair_value_gaps": [...],
            "fair_value_gaps_total": int,
            "liquidity_pools": [...],
            "liquidity_sweeps": [...],
            "liquidity_sweeps_total": int
        }

        On failure (e.g. no cached candles yet for this venue/symbol/timeframe —
        check list_market_symbols first): {"error": "<message>"}.
    """
    try:
        response = await _request(
            "GET", "/structure", params={"venue": venue, "symbol": symbol, "timeframe": timeframe}
        )
        result = response.json()
    except BackendError as exc:
        return _err(str(exc))

    for field in (
        "swing_points",
        "structure_events",
        "order_blocks",
        "fair_value_gaps",
        "liquidity_sweeps",
    ):
        trimmed, total = _trim(result.get(field, []), max_items)
        result[field] = trimmed
        result[f"{field}_total"] = total

    return _ok(result)


@mcp.tool(
    title="Get Confluence Trade Signal",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def get_trade_signal(
    venue: Venue,
    symbol: str,
    timeframe: str = "1m",
    account_balance: Optional[float] = None,
    risk_pct: Optional[float] = None,
) -> str:
    """Get the current SMC + Elliott Wave confluence trade signal for one
    venue/symbol/timeframe, if one is firing right now. A signal only fires
    when at least two distinct analysis schools (SMC structure, liquidity,
    Elliott Wave) agree on direction AND the ATR-based risk plan clears the
    backend's minimum risk:reward gate — most of the time this returns "no
    signal", which is expected and not an error.

    Args:
        venue: One of "binance", "bybit", "oanda", "polygon", "tradingview".
        symbol: Exchange-native symbol, e.g. "btcusdt" or "EUR_USD".
        timeframe: Candle interval, e.g. "1m", "5m", "1h". Default "1m".
        account_balance: Override the account size (in quote currency) used
            to size the position. Falls back to the backend's configured
            default (DEFAULT_ACCOUNT_BALANCE, $10,000 unless overridden)
            when omitted.
        risk_pct: Override the fraction of account_balance risked if the
            stop-loss is hit, e.g. 0.01 for 1%. Falls back to the backend's
            configured default (DEFAULT_RISK_PCT) when omitted.

    Returns:
        JSON object when a signal fires:
        {
            "symbol": str, "venue": str, "timeframe": str,
            "direction": "long" | "short",
            "ts": ISO-8601 timestamp,
            "confluences": [{"school": "smc"|"elliott"|"liquidity", "description": str, "weight": float}],
            "confluence_score": float,
            "risk": {
                "entry": float, "stop_loss": float,
                "take_profits": [float, ...], "risk_reward": [float, ...],
                "atr": float, "account_balance": float, "risk_pct": float,
                "risk_amount": float,
                "position_size": float   # units sized so a stop-out loses exactly risk_amount
            },
            "note": str | null
        }

        {"signal": null} when SMC/Elliott/liquidity don't currently agree
        (no trade to take — this is normal, not a failure).

        On failure (e.g. no cached candles yet — check list_market_symbols
        first): {"error": "<message>"}.
    """
    try:
        response = await _request(
            "GET",
            "/signals",
            params={
                "venue": venue,
                "symbol": symbol,
                "timeframe": timeframe,
                "account_balance": account_balance,
                "risk_pct": risk_pct,
            },
        )
    except BackendError as exc:
        return _err(str(exc))

    signal = response.json()
    if signal is None:
        return _ok({"signal": None})
    return _ok(signal)


@mcp.tool(
    title="Generate And Push Trade Signal Alert",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
)
async def notify_trade_signal(
    venue: Venue,
    symbol: str,
    timeframe: str = "1m",
    account_balance: Optional[float] = None,
    risk_pct: Optional[float] = None,
) -> str:
    """Generate a confluence trade signal exactly like get_trade_signal, and
    — if one fires — push it to whichever alert channels are configured on
    the backend (Telegram and/or Discord). Side-effecting: calling this
    repeatedly with the same inputs while a signal is active will re-send
    the notification each time, so prefer get_trade_signal for read-only
    checks and only call this tool when you actually want an alert
    delivered.

    Args:
        venue: One of "binance", "bybit", "oanda", "polygon", "tradingview".
        symbol: Exchange-native symbol, e.g. "btcusdt" or "EUR_USD".
        timeframe: Candle interval. Default "1m".
        account_balance: Override account size for position sizing. Optional.
        risk_pct: Override risk fraction per trade. Optional.

    Returns:
        JSON object:
        {
            "signal": <TradeSignal object, see get_trade_signal> | null,
            "delivered": {"telegram": bool, "discord": bool, ...}
            # "delivered" is {} when no signal fired, or when neither
            # TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID nor DISCORD_WEBHOOK_URL
            # is configured on the backend.
        }

        On failure: {"error": "<message>"}.
    """
    try:
        response = await _request(
            "POST",
            "/signals/notify",
            params={
                "venue": venue,
                "symbol": symbol,
                "timeframe": timeframe,
                "account_balance": account_balance,
                "risk_pct": risk_pct,
            },
        )
        return _ok(response.json())
    except BackendError as exc:
        return _err(str(exc))


@mcp.tool(
    title="Analyze Chart Screenshot",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def analyze_chart_report(
    image_path: str,
    symbol: Optional[str] = None,
    account_balance: Optional[float] = None,
    risk_pct: Optional[float] = None,
) -> str:
    """Upload a local TradingView chart screenshot and get back a structured
    SMC/Price-Action analyst report: market structure, a trade setup
    (bias/entry/stop/targets), a computed risk-management plan (position
    size is always calculated server-side from the model's entry/stop,
    never invented by the vision model), and a conviction rating with
    reasoning. Requires the backend to have ANTHROPIC_API_KEY or
    OPENAI_API_KEY configured; if neither is set, this returns a clear
    error rather than a fabricated report. This is a technical read of the
    chart, not individualized investment advice.

    Args:
        image_path: Absolute path to a local chart screenshot (PNG/JPEG,
            <= 8MB). The file is read and uploaded to the backend.
        symbol: Optional symbol label to attach to the report (e.g.
            "BTCUSDT") — informational only, doesn't change the analysis.
        account_balance: Override account size for the risk_management
            section's position sizing. Falls back to the backend default.
        risk_pct: Override risk fraction per trade. Falls back to the
            backend default.

    Returns:
        JSON object:
        {
            "symbol": str | null,
            "market_structure": {"trend": "bullish"|"bearish"|"sideways", "key_structure": [str, ...]},
            "trade_setup": {"bias": "bullish"|"bearish"|"neutral", "entry": float|null,
                             "stop_loss": float|null, "take_profits": [float, ...]},
            "risk_management": {"account_balance": float, "risk_pct": float,
                                 "max_risk_amount": float, "position_size": float|null,
                                 "risk_reward": float|null},
            "conviction": {"confidence": "High"|"Medium"|"Low", "reasoning": [str, ...]},
            "provider": str   # which vision model produced the report
        }

        On failure (file not found/too large, backend unreachable, or no
        vision provider configured / response didn't parse into a report):
        {"error": "<message>"}.
    """
    path = Path(image_path).expanduser()
    if not path.is_file():
        return _err(f"No such file: {path}")

    try:
        size = path.stat().st_size
    except OSError as exc:
        return _err(f"Could not stat {path}: {exc}")
    if size > MAX_UPLOAD_BYTES:
        return _err(
            f"{path} is {size} bytes, which exceeds the backend's "
            f"{MAX_UPLOAD_BYTES} byte upload limit for chart images."
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _err(f"Could not read {path}: {exc}")

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    files = {"image": (path.name, raw, mime_type)}
    form: dict[str, Any] = {}
    if symbol is not None:
        form["symbol"] = symbol
    if account_balance is not None:
        form["account_balance"] = account_balance
    if risk_pct is not None:
        form["risk_pct"] = risk_pct

    try:
        response = await _request(
            "POST",
            "/analyze-chart/report",
            data=form,
            files=files,
            timeout=REPORT_TIMEOUT,
        )
        return _ok(response.json())
    except BackendError as exc:
        return _err(str(exc))


@mcp.tool(
    title="Send TradingView Webhook Alert",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def send_tradingview_alert(
    symbol: str,
    timeframe: str,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 0.0,
    secret: Optional[str] = None,
) -> str:
    """Feed one OHLCV bar into the backend as if it came from a TradingView
    `alert()` webhook. Useful for backfilling a symbol that has no dedicated
    exchange ingestion feed wired up (e.g. a custom TradingView symbol), or
    for testing the webhook ingestion path end to end. The bar becomes
    immediately queryable via list_market_symbols / get_market_structure /
    get_trade_signal under venue="tradingview".

    Args:
        symbol: Symbol as it should be stored, e.g. "btcusdt". Lower-cased
            by the backend.
        timeframe: Candle interval label, e.g. "1m", "5m", "1h".
        open: Bar open price.
        high: Bar high price.
        low: Bar low price.
        close: Bar close price.
        volume: Bar volume. Default 0.0.
        secret: Shared webhook secret. If omitted, falls back to the
            NEXUSTRADE_WEBHOOK_SECRET environment variable. Only required
            if the backend has TRADINGVIEW_WEBHOOK_SECRET configured — if
            it doesn't, any value (including none) is accepted.

    Returns:
        JSON object: {"status": "accepted", "symbol": str, "timeframe": str}

        On failure (e.g. 401 for a missing/incorrect secret when the
        backend requires one): {"error": "<message>"}.
    """
    effective_secret = secret or WEBHOOK_SECRET
    try:
        response = await _request(
            "POST",
            "/webhook/tradingview",
            params={"secret": effective_secret},
            json_body={
                "symbol": symbol,
                "timeframe": timeframe,
                "open": open,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
        )
        return _ok(response.json())
    except BackendError as exc:
        return _err(str(exc))


@mcp.tool(
    title="Check Backend Status",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
)
async def check_backend_status() -> str:
    """Check whether the NexusTrade AI backend is reachable and healthy.
    Useful as a first diagnostic step if other tools are returning
    connectivity errors, or to confirm which backend URL this MCP server
    is actually configured to talk to.

    Returns:
        JSON object: {"reachable": true, "backend_url": str, "status": "ok", "service": str}
        or {"reachable": false, "backend_url": str, "error": "<message>"}.
    """
    try:
        response = await _request("GET", "/health")
        return _ok({"reachable": True, "backend_url": BACKEND_URL, **response.json()})
    except BackendError as exc:
        return _ok({"reachable": False, "backend_url": BACKEND_URL, "error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
