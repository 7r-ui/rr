from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NexusTrade AI"
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://nexustrade:nexustrade@localhost:5432/nexustrade"

    candle_persist_batch_size: int = 50
    candle_persist_interval_seconds: float = 5.0
    signal_scan_interval_seconds: float = 30.0

    binance_ws_url: str = "wss://stream.binance.com:9443/stream"
    bybit_ws_url: str = "wss://stream.bybit.com/v5/public/linear"

    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_base_url: str = "https://api-fxpractice.oanda.com"

    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"

    vision_provider: str = "openai"  # "openai" | "none"
    openai_api_key: str = ""
    vision_model: str = "gpt-4o-mini"

    default_symbols_crypto: list[str] = ["btcusdt", "ethusdt"]
    default_symbols_fx: list[str] = ["EUR_USD", "XAU_USD"]

    min_risk_reward: float = 2.0
    atr_period: int = 14
    atr_stop_multiple: float = 1.5

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
