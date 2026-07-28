from functools import lru_cache
from typing import Literal

from app2.config.logging import setup_logging
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    ENABLE_CACHE: bool = True
    CACHE_PREFIX: str = "app2:"

    # TTLs
    REDIS_TTL_SEARCH: int = 3600
    REDIS_TTL_EMBEDDING: int = 86400

    # Logging
    LOG_LEVEL: str = "INFO"

    def setup(self):
        setup_logging(self.LOG_LEVEL)


@lru_cache
def get_settings() -> Settings:
    return Settings()
