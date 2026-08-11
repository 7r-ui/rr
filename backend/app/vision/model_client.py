"""Pluggable multimodal vision model client for chart interpretation.

Calls an OpenAI-compatible vision chat-completions endpoint (default
gpt-4o-mini) with the uploaded chart image and asks for a structured list of
graphical indicators/SMC patterns it can identify, in normalized [0,1]
image-fraction coordinates (model-estimated, not pixel-exact - always lower
confidence than the OpenCV Hough detections). Returns [] rather than raising
when no provider is configured, so /analyze-chart still works on the
deterministic OpenCV path alone.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx

from app.core.config import get_settings
from app.models.schemas import DetectedLevel

logger = logging.getLogger(__name__)

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
    if settings.vision_provider != "openai" or not settings.openai_api_key:
        logger.info("No vision model configured; skipping model-based chart analysis.")
        return []

    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": settings.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1000,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("Vision model call failed: %s", exc)
        return []

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Vision model returned unparsable content: %s", exc)
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
