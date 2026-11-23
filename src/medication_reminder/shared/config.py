from functools import lru_cache
from typing import Literal

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEDICATION_",
        extra="ignore",
    )

    app_name: str = "Medication Reminder"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "postgresql+asyncpg://medication:medication@localhost:5432/medication"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: SecretStr | None = None
    telegram_mini_app_url: str | None = None
    telegram_admin_ids: tuple[int, ...] = ()
    local_session_allow_docker_bridge: bool = False

    @field_validator("telegram_admin_ids")
    @classmethod
    def validate_admin_ids(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(item <= 0 for item in value):
            raise ValueError("Telegram admin IDs must be positive")
        return value

    reminder_batch_size: int = 50
    reminder_poll_interval_seconds: float = 10.0
    reminder_retry_interval_seconds: int = 60
    reminder_claim_timeout_seconds: int = 300
    reminder_max_consecutive_failures: int = 6
    reminder_attempt_retention_days: int = 90
    schedule_horizon_days: int = 90

    @field_validator(
        "reminder_batch_size",
        "reminder_retry_interval_seconds",
        "reminder_claim_timeout_seconds",
        "reminder_max_consecutive_failures",
        "reminder_attempt_retention_days",
        "schedule_horizon_days",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("reminder worker settings must be positive")
        return value

    @field_validator("reminder_poll_interval_seconds")
    @classmethod
    def validate_positive_interval(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("reminder_poll_interval_seconds must be positive")
        return value

    @field_validator("telegram_mini_app_url", mode="before")
    @classmethod
    def validate_mini_app_url(cls, value: object) -> object:
        if value in (None, ""):
            return None
        if not isinstance(value, str):
            raise ValueError("telegram_mini_app_url must be an HTTPS URL")
        parsed = HttpUrl(value)
        if parsed.scheme != "https":
            raise ValueError("telegram_mini_app_url must be an HTTPS URL")
        return str(parsed)


@lru_cache
def get_settings() -> Settings:
    return Settings()
