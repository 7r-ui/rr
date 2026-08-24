"""Best-effort Telegram/Discord delivery for a generated TradeSignal.

Both channels are opt-in via config (empty token/webhook = skipped). A
delivery failure is logged, never raised — an alert channel being down must
not take down the signal endpoint that triggered it.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.models.schemas import TradeSignal

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def format_signal_message(signal: TradeSignal) -> str:
    risk = signal.risk
    tps = ", ".join(f"{tp:g}" for tp in risk.take_profits)
    rrs = ", ".join(f"1:{rr:.2f}" for rr in risk.risk_reward)
    confluences = "\n".join(f"  • {f.school}: {f.description}" for f in signal.confluences)
    return (
        f"{signal.direction.value.upper()} {signal.symbol} ({signal.venue.value}, {signal.timeframe})\n"
        f"Entry: {risk.entry:g}\n"
        f"Stop Loss: {risk.stop_loss:g}\n"
        f"Take Profits: {tps}\n"
        f"R:R: {rrs}\n"
        f"Risk: {risk.risk_amount:g} ({risk.risk_pct:.1%} of {risk.account_balance:g}) "
        f"→ size {risk.position_size:g}\n"
        f"Confluence score: {signal.confluence_score:.2f}\n"
        f"{confluences}\n"
        f"Not individualized investment advice — technical confluence output only."
    )


async def _send_telegram(text: str) -> bool:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {"chat_id": settings.telegram_chat_id, "text": text}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram alert delivery failed: %s", exc)
        return False


async def _send_discord(text: str) -> bool:
    settings = get_settings()
    if not settings.discord_webhook_url:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.discord_webhook_url, json={"content": text})
            resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Discord alert delivery failed: %s", exc)
        return False


async def dispatch_signal_alert(signal: TradeSignal) -> dict[str, bool]:
    text = format_signal_message(signal)
    return {
        "telegram": await _send_telegram(text),
        "discord": await _send_discord(text),
    }
