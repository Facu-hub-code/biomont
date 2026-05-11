"""Settings compartidos.

Cada servicio puede extender estos bloques con su propio `Settings`. Los
valores se cargan desde variables de entorno y desde `.env` cuando esta
presente.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Datos de conexion al Postgres remoto (Railway)."""

    database_url: SecretStr = Field(..., alias="DATABASE_URL")
    pool_min_size: int = Field(1, alias="DB_POOL_MIN_SIZE")
    pool_max_size: int = Field(10, alias="DB_POOL_MAX_SIZE")
    statement_timeout_ms: int = Field(15_000, alias="DB_STATEMENT_TIMEOUT_MS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class OpenAISettings(BaseSettings):
    """Credenciales y modelos OpenAI."""

    api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    chat_model: str = Field("gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    embeddings_model: str = Field(
        "text-embedding-3-small", alias="OPENAI_EMBEDDINGS_MODEL"
    )
    embeddings_dim: int = 1536
    request_timeout_s: float = Field(30.0, alias="OPENAI_REQUEST_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class LoggingSettings(BaseSettings):
    """Logging estructurado (structlog)."""

    level: str = Field("INFO", alias="LOG_LEVEL")
    json_output: bool = Field(True, alias="LOG_JSON")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    return OpenAISettings()


@lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()
