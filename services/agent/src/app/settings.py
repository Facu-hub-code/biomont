"""Settings especificas del agente."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WhatsAppSettings(BaseSettings):
    phone_number_id: str = Field(..., alias="WHATSAPP_PHONE_NUMBER_ID")
    access_token: SecretStr = Field(..., alias="WHATSAPP_ACCESS_TOKEN")
    verify_token: SecretStr = Field(..., alias="WHATSAPP_VERIFY_TOKEN")
    app_secret: SecretStr = Field(..., alias="WHATSAPP_APP_SECRET")
    graph_api_version: str = Field("v20.0", alias="WHATSAPP_GRAPH_API_VERSION")
    enable_outbound: bool = Field(True, alias="WHATSAPP_ENABLE_OUTBOUND")
    webhook_agent_enabled: bool = Field(
        True, alias="WHATSAPP_WEBHOOK_AGENT_ENABLED"
    )
    webhook_skip_signature_verify: bool = Field(
        False, alias="WHATSAPP_WEBHOOK_SKIP_SIGNATURE_VERIFY"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class AgentSettings(BaseSettings):
    similarity_threshold: float = Field(
        0.75, alias="AGENT_SIMILARITY_THRESHOLD"
    )
    top_k: int = Field(6, alias="AGENT_TOP_K")
    system_prompt_cache_ttl_seconds: int = Field(
        60, alias="AGENT_SYSTEM_PROMPT_CACHE_TTL_SECONDS"
    )
    playground_secret: SecretStr | None = Field(
        None, alias="AGENT_PLAYGROUND_SECRET"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_whatsapp_settings() -> WhatsAppSettings:
    return WhatsAppSettings()


@lru_cache(maxsize=1)
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
