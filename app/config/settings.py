from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./information_engine.db"
    redis_url: str = "redis://localhost:6379/0"
    http_timeout_seconds: float = 20
    fetch_retry_attempts: int = 3
    fetch_backoff_seconds: float = 1.5
    scheduler_enabled: bool = False
    fred_api_key: str | None = None
    sec_user_agent: str = Field(
        default="information-engine/0.1 contact@example.com",
        description="SEC requires a descriptive User-Agent.",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

