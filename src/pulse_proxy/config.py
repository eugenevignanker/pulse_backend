"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets must be supplied by deployment tooling, not Git."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    token_ttl_seconds: int = 3600
    token_store_path: Path = Path("var/tokens")
    user_store_path: Path = Path("var/users")
    proxy_token_signing_key: SecretStr | None = None
    alpaca_environment: Literal["paper", "live"] = "paper"
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_live_base_url: str = "https://api.alpaca.markets"
    alpaca_api_key_id: str | None = None
    alpaca_api_secret: SecretStr | None = None
    auth_verify_timeout_ms: int = 500
    alpaca_connect_timeout_ms: int = 2000
    alpaca_read_timeout_ms: int = 10000
