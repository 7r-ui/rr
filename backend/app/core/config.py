from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NexusTrade AI"
    redis_url: str = "redis://localhost:6379/0"

    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    bybit_ws_url: str = "wss://stream.bybit.com/v5/public/linear"

    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_base_url: str = "https://api-fxpractice.oanda.com"

    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"

    vision_provider: str = "openai"  # "openai" | "anthropic" | "none"
    openai_api_key: str = ""
    vision_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    default_symbols_crypto: list[str] = ["btcusdt", "ethusdt"]
    default_symbols_fx: list[str] = ["EUR_USD", "XAU_USD"]

    min_risk_reward: float = 2.0
    atr_period: int = 14
    atr_stop_multiple: float = 1.5

    default_account_balance: float = 10000.0
    default_risk_pct: float = 0.01

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # Shared secret a TradingView alert webhook must echo back (as
    # `?secret=` or an `X-Webhook-Secret` header) before its OHLCV payload
    # is trusted. Empty disables auth entirely — fine for local dev only.
    tradingview_webhook_secret: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
