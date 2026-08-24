"""Pluggable multimodal vision model client for chart interpretation.

Supports Claude (Anthropic Messages API) and any OpenAI-compatible vision
chat-completions endpoint (default gpt-4o-mini), selected by
`settings.vision_provider`. `analyze_chart_with_vision_model` asks for a
structured list of graphical indicators/SMC patterns in normalized [0,1]
image-fraction coordinates (model-estimated, not pixel-exact — always lower
confidence than the OpenCV Hough detections) and returns [] rather than
raising when no provider is configured, so /analyze-chart still works on the
deterministic OpenCV path alone. `generate_full_report` runs the full
SMC/Price-Action structured-report prompt and returns a ChartReport (or None
if unconfigured/unparsable — never a fabricated report).
"""
from __future__ import annotations

import base64
import json
import logging

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schemas import (
    ChartReport,
    ConvictionSection,
    DetectedLevel,
    MarketStructureSection,
    RiskManagementSection,
    TradeSetupSection,
)

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

VISION_PROMPT = """You are a chart-reading assistant for a trading platform.
Given this candlestick chart screenshot, identify visible support/resistance
levels, order blocks, and fair value gaps. Respond ONLY with JSON matching:
{"levels": [{"label": "support|resistance|order_block|fvg|trendline",
"y_fraction": 0.0-1.0, "y_fraction_end": 0.0-1.0 (optional, for a range),
"confidence": 0.0-1.0}]}
y_fraction is the vertical position as a fraction of image height from the
top. If uncertain, return fewer, higher-confidence levels rather than many
guesses."""


async def analyze_chart_with_vision_model(
    image_bytes: bytes, *, image_height: int, image_width: int
) -> list[DetectedLevel]:
    settings = get_settings()
    if settings.vision_provider == "anthropic" and settings.anthropic_api_key:
        raw = await _call_anthropic(VISION_PROMPT, image_bytes)
    elif settings.vision_provider == "openai" and settings.openai_api_key:
        raw = await _call_openai(VISION_PROMPT, image_bytes)
    else:
        logger.info("No vision model configured; skipping model-based chart analysis.")
        return []

    parsed = _parse_json_object(raw)
    if parsed is None:
        return []

    levels: list[DetectedLevel] = []
    for item in parsed.get("levels", []):
        y_frac = item.get("y_fraction")
        if y_frac is None:
            continue
        y_px = int(float(y_frac) * image_height)
        y_end_frac = item.get("y_fraction_end")
        y_end_px = int(float(y_end_frac) * image_height) if y_end_frac is not None else y_px
        levels.append(
            DetectedLevel(
                label=item.get("label", "support"),
                pixel_bbox=(0, min(y_px, y_end_px), image_width, max(y_px, y_end_px)),
                confidence=float(item.get("confidence", 0.5)),
            )
        )
    return levels


def _parse_json_object(raw: str | None) -> dict | None:
    if raw is None:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as exc:
        logger.warning("Vision model returned unparsable JSON: %s", exc)
        return None


async def _call_openai(prompt: str, image_bytes: bytes, *, max_tokens: int = 1000) -> str | None:
    settings = get_settings()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("OpenAI vision call failed: %s", exc)
        return None

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.warning("OpenAI vision response missing expected content: %s", exc)
        return None


async def _call_anthropic(prompt: str, image_bytes: bytes, *, max_tokens: int = 1500) -> str | None:
    settings = get_settings()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Anthropic vision call failed: %s", exc)
        return None

    try:
        return "".join(
            block["text"] for block in data["content"] if block.get("type") == "text"
        )
    except (KeyError, TypeError) as exc:
        logger.warning("Anthropic vision response missing expected content: %s", exc)
        return None


FULL_REPORT_PROMPT_TEMPLATE = """Act as a professional Smart Money Concepts (SMC) & Price Action \
crypto/forex analyst.

Analyze the provided chart screenshot carefully and respond with ONLY a JSON object (no markdown \
fences, no commentary before or after) matching exactly this shape:

{{
  "market_structure": {{
    "trend": "bullish" | "bearish" | "sideways",
    "key_structure": ["short strings: breakout, pullback, CHoCH, liquidity sweep, support/resistance levels seen"]
  }},
  "trade_setup": {{
    "bias": "bullish" | "bearish" | "neutral",
    "entry": number or null,
    "stop_loss": number or null,
    "take_profits": [number, ...]
  }},
  "conviction": {{
    "confidence": "High" | "Medium" | "Low",
    "reasoning": ["short strings explaining why this trade, e.g. volume confirmation, channel breakout, key zone reaction"]
  }}
}}

Place stop_loss beyond the nearest structural invalidation point (below a local low / structural \
swing for a bullish bias, above one for bearish). If you cannot confidently read a price level off \
the image's axis, use null for that field rather than guessing — do not fabricate numbers.
This is a technical/engineering read of the chart, not individualized financial advice."""


def _build_risk_management(
    trade_setup: TradeSetupSection, *, account_balance: float, risk_pct: float
) -> RiskManagementSection:
    max_risk_amount = account_balance * risk_pct
    position_size = None
    risk_reward = None
    if trade_setup.entry is not None and trade_setup.stop_loss is not None:
        risk_per_unit = abs(trade_setup.entry - trade_setup.stop_loss)
        if risk_per_unit > 0:
            position_size = max_risk_amount / risk_per_unit
            if trade_setup.take_profits:
                reward_per_unit = abs(trade_setup.take_profits[0] - trade_setup.entry)
                risk_reward = reward_per_unit / risk_per_unit
    return RiskManagementSection(
        account_balance=account_balance,
        risk_pct=risk_pct,
        max_risk_amount=max_risk_amount,
        position_size=position_size,
        risk_reward=risk_reward,
    )


async def generate_full_report(
    image_bytes: bytes,
    *,
    symbol: str | None,
    account_balance: float,
    risk_pct: float,
) -> ChartReport | None:
    """Runs the full SMC/Price-Action structured-report prompt against
    whichever provider is configured, preferring Claude when both an
    Anthropic and an OpenAI key are set. Returns None (never a fabricated
    report) if no provider is configured or the model's output doesn't
    parse into the expected schema."""
    settings = get_settings()
    prompt = FULL_REPORT_PROMPT_TEMPLATE
    if settings.anthropic_api_key:
        provider = "anthropic"
        raw = await _call_anthropic(prompt, image_bytes)
    elif settings.openai_api_key:
        provider = "openai"
        raw = await _call_openai(prompt, image_bytes, max_tokens=1500)
    else:
        logger.info("No vision model configured; cannot generate a full chart report.")
        return None

    parsed = _parse_json_object(raw)
    if parsed is None:
        return None

    try:
        market_structure = MarketStructureSection(**parsed["market_structure"])
        trade_setup = TradeSetupSection(**parsed["trade_setup"])
        conviction = ConvictionSection(**parsed["conviction"])
    except (KeyError, ValidationError) as exc:
        logger.warning("Model report didn't match expected schema: %s", exc)
        return None

    risk_management = _build_risk_management(
        trade_setup, account_balance=account_balance, risk_pct=risk_pct
    )

    return ChartReport(
        symbol=symbol,
        market_structure=market_structure,
        trade_setup=trade_setup,
        risk_management=risk_management,
        conviction=conviction,
        provider=provider,
    )
