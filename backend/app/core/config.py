"""Runtime configuration, loaded exclusively from environment variables.

Every value that differs between environments lives here. Nothing in the codebase reads
``os.environ`` directly, so this module is the complete inventory of the API's configuration.
"""

from datetime import timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


_PLACEHOLDER_MARKERS = ("change-me", "changeme", "your-", "example")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    environment: Environment = Environment.PRODUCTION
    log_level: str = "INFO"

    # Runtime connection. Must use the least-privileged application role, never the owner.
    database_url: SecretStr
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=100)

    # Used to derive CSRF tokens. Rotating it invalidates every CSRF token, not sessions.
    secret_key: SecretStr = Field(min_length=32)

    # Origins allowed to make credentialed cross-origin requests. Same-origin traffic
    # (frontend served behind the same host as /api) never needs to be listed here.
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    session_cookie_secure: bool = True
    session_idle_timeout_minutes: int = Field(default=60 * 24, ge=5)
    session_absolute_timeout_days: int = Field(default=14, ge=1, le=90)

    invitation_ttl_days: int = Field(default=7, ge=1, le=30)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("allowed_origins")
    @classmethod
    def _reject_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard origins are incompatible with credentialed requests")
        return value

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Settings:
        if self.environment is not Environment.PRODUCTION:
            return self
        secret = self.secret_key.get_secret_value().lower()
        if any(marker in secret for marker in _PLACEHOLDER_MARKERS):
            raise ValueError("SECRET_KEY still holds a placeholder value")
        if not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        return self

    @property
    def is_development(self) -> bool:
        return self.environment is Environment.DEVELOPMENT

    @property
    def session_idle_timeout(self) -> timedelta:
        return timedelta(minutes=self.session_idle_timeout_minutes)

    @property
    def session_absolute_timeout(self) -> timedelta:
        return timedelta(days=self.session_absolute_timeout_days)

    @property
    def invitation_ttl(self) -> timedelta:
        return timedelta(days=self.invitation_ttl_days)

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes the browser refuse the cookie unless it is Secure,
        # host-only and scoped to "/", which blocks subdomain cookie-injection attacks.
        return "__Host-georgos_session" if self.session_cookie_secure else "georgos_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # populated from the environment
