"""Settings especificas del backoffice-api."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackofficeApiSettings(BaseSettings):
    jwt_secret: SecretStr = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(480, alias="JWT_EXPIRATION_MINUTES")

    cors_origins: str = Field(
        "http://localhost:3000",
        alias="BACKOFFICE_API_CORS_ORIGINS",
    )

    agent_internal_base_url: str = Field(
        "http://localhost:8001",
        alias="AGENT_INTERNAL_BASE_URL",
    )
    agent_playground_secret: SecretStr | None = Field(
        None,
        alias="AGENT_PLAYGROUND_SECRET",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_backoffice_settings() -> BackofficeApiSettings:
    return BackofficeApiSettings()
